import mimetypes
from zipfile import BadZipFile

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import FileResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response

from api.v1.exceptions import CodedAPIException
from audit.models import CourseHistoryAction, CourseHistoryObjectType
from audit.services import record_course_history_event
from courses.models import Course
from courses.permissions import CourseAccessPermission, courses_accessible_to
from learning.models import (
    CourseModule,
    CourseTopic,
    LearningMaterial,
    LearningMaterialType,
    Lesson,
    ReleaseType,
    ScormPackage,
    VideoProcessingStatus,
)
from learning.permissions import (
    MaterialPermission,
    StructureManagePermission,
    StructureObjectPermission,
    course_content_accessible_to,
)
from learning.reordering import reorder_structure
from learning.scorm import stream_scorm_member

from .serializers import (
    CourseMaterialFilterSerializer,
    CourseModuleWriteSerializer,
    CourseStructureSerializer,
    CourseTopicWriteSerializer,
    DeleteConfirmationSerializer,
    LessonWriteSerializer,
    LearningMaterialSerializer,
    ScormPackageSerializer,
    StructureReorderSerializer,
)


class StructureNotEmpty(CodedAPIException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "structure_not_empty"
    default_detail = "Structure contains nested objects. Confirm cascade deletion."


class LessonIsRequired(CodedAPIException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "lesson_is_required"
    default_detail = "Lesson is required by another lesson."


def record_material_event(material, action, actor):
    record_course_history_event(
        course=material.course,
        action=action,
        actor=actor,
        object_type=CourseHistoryObjectType.MATERIAL,
        object_id=material.pk,
        object_title=material.title,
        details={"material_type": material.type},
    )


def course_structure_queryset():
    lessons = Lesson.objects.select_related("required_lesson").order_by(
        "order",
        "id",
    )
    topics = CourseTopic.objects.order_by("order", "id").prefetch_related(
        Prefetch("lessons", queryset=lessons)
    )
    modules = CourseModule.objects.order_by("order", "id").prefetch_related(
        Prefetch("topics", queryset=topics)
    )
    return Course.objects.prefetch_related(Prefetch("modules", queryset=modules))


class CourseStructureView(generics.RetrieveAPIView):
    permission_classes = (CourseAccessPermission,)
    serializer_class = CourseStructureSerializer

    def get_queryset(self):
        return courses_accessible_to(
            self.request.user,
            course_structure_queryset(),
        )


class CourseModuleCreateView(generics.CreateAPIView):
    permission_classes = (StructureManagePermission,)
    serializer_class = CourseModuleWriteSerializer

    def get_course(self):
        course = get_object_or_404(
            courses_accessible_to(self.request.user),
            pk=self.kwargs["course_pk"],
        )
        self.check_object_permissions(self.request, course)
        return course

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["course"] = self.get_course()
        return context


class CourseModuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    http_method_names = ("patch", "delete", "options")
    permission_classes = (StructureManagePermission,)
    serializer_class = CourseModuleWriteSerializer

    def get_queryset(self):
        accessible_courses = courses_accessible_to(self.request.user)
        return CourseModule.objects.select_related("course").filter(
            course__in=accessible_courses
        )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        confirmation = DeleteConfirmationSerializer(data=request.data)
        confirmation.is_valid(raise_exception=True)
        if instance.topics.exists() and not confirmation.validated_data["confirm"]:
            raise StructureNotEmpty()
        module_lessons = Lesson.objects.filter(topic__module=instance)
        has_external_dependents = (
            Lesson.objects.filter(required_lesson__in=module_lessons)
            .exclude(topic__module=instance)
            .exists()
        )
        if has_external_dependents:
            raise StructureNotEmpty(
                "Module lessons are prerequisites for lessons outside the module."
            )
        module_lessons.filter(required_lesson__isnull=False).update(
            required_lesson=None,
            release_type=ReleaseType.ALWAYS,
            release_at=None,
        )
        for material in LearningMaterial.objects.filter(lesson__in=module_lessons):
            record_material_event(
                material,
                CourseHistoryAction.MATERIAL_DELETED,
                request.user,
            )
        for lesson in module_lessons:
            record_course_history_event(
                course=instance.course,
                action=CourseHistoryAction.LESSON_DELETED,
                actor=request.user,
                object_type=CourseHistoryObjectType.LESSON,
                object_id=lesson.pk,
                object_title=lesson.title,
            )
        for topic in instance.topics.all():
            record_course_history_event(
                course=instance.course,
                action=CourseHistoryAction.TOPIC_DELETED,
                actor=request.user,
                object_type=CourseHistoryObjectType.TOPIC,
                object_id=topic.pk,
                object_title=topic.title,
            )
        record_course_history_event(
            course=instance.course,
            action=CourseHistoryAction.MODULE_DELETED,
            actor=request.user,
            object_type=CourseHistoryObjectType.MODULE,
            object_id=instance.pk,
            object_title=instance.title,
        )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CourseTopicCreateView(generics.CreateAPIView):
    permission_classes = (StructureManagePermission,)
    serializer_class = CourseTopicWriteSerializer

    def get_module(self):
        accessible_courses = courses_accessible_to(self.request.user)
        module = get_object_or_404(
            CourseModule.objects.select_related("course").filter(
                course__in=accessible_courses
            ),
            pk=self.kwargs["module_pk"],
        )
        self.check_object_permissions(self.request, module)
        return module

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["module"] = self.get_module()
        return context


class CourseTopicDetailView(generics.RetrieveUpdateDestroyAPIView):
    http_method_names = ("patch", "delete", "options")
    permission_classes = (StructureManagePermission,)
    serializer_class = CourseTopicWriteSerializer

    def get_queryset(self):
        accessible_courses = courses_accessible_to(self.request.user)
        return CourseTopic.objects.select_related(
            "module",
            "module__course",
        ).filter(module__course__in=accessible_courses)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        confirmation = DeleteConfirmationSerializer(data=request.data)
        confirmation.is_valid(raise_exception=True)
        if instance.lessons.exists() and not confirmation.validated_data["confirm"]:
            raise StructureNotEmpty()
        topic_lessons = Lesson.objects.filter(topic=instance)
        has_external_dependents = (
            Lesson.objects.filter(required_lesson__in=topic_lessons)
            .exclude(topic=instance)
            .exists()
        )
        if has_external_dependents:
            raise StructureNotEmpty(
                "Topic lessons are prerequisites for lessons outside the topic."
            )
        topic_lessons.filter(required_lesson__isnull=False).update(
            required_lesson=None,
            release_type=ReleaseType.ALWAYS,
            release_at=None,
        )
        for material in LearningMaterial.objects.filter(lesson__in=topic_lessons):
            record_material_event(
                material,
                CourseHistoryAction.MATERIAL_DELETED,
                request.user,
            )
        for lesson in topic_lessons:
            record_course_history_event(
                course=instance.module.course,
                action=CourseHistoryAction.LESSON_DELETED,
                actor=request.user,
                object_type=CourseHistoryObjectType.LESSON,
                object_id=lesson.pk,
                object_title=lesson.title,
            )
        record_course_history_event(
            course=instance.module.course,
            action=CourseHistoryAction.TOPIC_DELETED,
            actor=request.user,
            object_type=CourseHistoryObjectType.TOPIC,
            object_id=instance.pk,
            object_title=instance.title,
        )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LessonCreateView(generics.CreateAPIView):
    permission_classes = (StructureManagePermission,)
    serializer_class = LessonWriteSerializer

    def get_topic(self):
        accessible_courses = courses_accessible_to(self.request.user)
        topic = get_object_or_404(
            CourseTopic.objects.select_related(
                "module",
                "module__course",
            ).filter(module__course__in=accessible_courses),
            pk=self.kwargs["topic_pk"],
        )
        self.check_object_permissions(self.request, topic)
        return topic

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["topic"] = self.get_topic()
        return context


class LessonDetailView(generics.RetrieveUpdateDestroyAPIView):
    http_method_names = ("get", "patch", "delete", "head", "options")
    permission_classes = (StructureObjectPermission,)
    serializer_class = LessonWriteSerializer

    def get_queryset(self):
        accessible_courses = courses_accessible_to(self.request.user)
        return Lesson.objects.select_related(
            "topic",
            "topic__module",
            "topic__module__course",
            "required_lesson",
            "created_by",
            "updated_by",
        ).filter(topic__module__course__in=accessible_courses)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.dependent_lessons.exists():
            raise LessonIsRequired()
        for material in instance.materials.all():
            record_material_event(
                material,
                CourseHistoryAction.MATERIAL_DELETED,
                request.user,
            )
        record_course_history_event(
            course=instance.topic.module.course,
            action=CourseHistoryAction.LESSON_DELETED,
            actor=request.user,
            object_type=CourseHistoryObjectType.LESSON,
            object_id=instance.pk,
            object_title=instance.title,
        )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StructureReorderView(generics.GenericAPIView):
    permission_classes = (StructureManagePermission,)
    serializer_class = StructureReorderSerializer

    def get_course(self):
        course = get_object_or_404(
            courses_accessible_to(self.request.user),
            pk=self.kwargs["pk"],
        )
        self.check_object_permissions(self.request, course)
        return course

    def post(self, request, *args, **kwargs):
        del args, kwargs
        course = self.get_course()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reorder_structure(
            course,
            serializer.validated_data["type"],
            serializer.validated_data["items"],
            request.user,
        )
        reordered_course = course_structure_queryset().get(pk=course.pk)
        return Response(CourseStructureSerializer(reordered_course).data)


def material_queryset_for(user):
    return LearningMaterial.objects.select_related(
        "course",
        "lesson",
        "lesson__topic",
        "lesson__topic__module",
    ).filter(course__in=course_content_accessible_to(user))


class LessonMaterialListCreateView(generics.ListCreateAPIView):
    permission_classes = (MaterialPermission,)
    serializer_class = LearningMaterialSerializer

    def get_lesson(self):
        lesson = get_object_or_404(
            Lesson.objects.select_related("topic__module__course").filter(
                topic__module__course__in=course_content_accessible_to(
                    self.request.user
                )
            ),
            pk=self.kwargs["lesson_pk"],
        )
        self.check_object_permissions(self.request, lesson)
        return lesson

    def get_queryset(self):
        return material_queryset_for(self.request.user).filter(lesson=self.get_lesson())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["lesson"] = self.get_lesson()
        return context

    @transaction.atomic
    def perform_create(self, serializer):
        lesson = self.get_lesson()
        material = serializer.save(
            lesson=lesson,
            course=lesson.course,
            created_by=self.request.user,
            updated_by=self.request.user,
        )
        record_material_event(
            material,
            CourseHistoryAction.MATERIAL_UPLOADED,
            self.request.user,
        )


class LearningMaterialDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (MaterialPermission,)
    serializer_class = LearningMaterialSerializer

    def get_queryset(self):
        return material_queryset_for(self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @transaction.atomic
    def perform_destroy(self, instance):
        record_material_event(
            instance,
            CourseHistoryAction.MATERIAL_DELETED,
            self.request.user,
        )
        instance.delete()


class CourseMaterialListView(generics.ListAPIView):
    permission_classes = (MaterialPermission,)
    serializer_class = LearningMaterialSerializer

    def get_course(self):
        course = get_object_or_404(
            course_content_accessible_to(self.request.user),
            pk=self.kwargs["pk"],
        )
        self.check_object_permissions(self.request, course)
        return course

    def get_queryset(self):
        filter_serializer = CourseMaterialFilterSerializer(
            data=self.request.query_params
        )
        filter_serializer.is_valid(raise_exception=True)
        filters = filter_serializer.validated_data
        queryset = material_queryset_for(self.request.user).filter(
            course=self.get_course()
        )
        search = filters.get("search")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(original_filename__icontains=search)
            )
        if "type" in filters:
            queryset = queryset.filter(type=filters["type"])
        if "lesson" in filters:
            queryset = queryset.filter(lesson_id=filters["lesson"])
        if "module" in filters:
            queryset = queryset.filter(lesson__topic__module_id=filters["module"])
        return queryset


class MaterialFileUnavailable(CodedAPIException):
    error_code = "material_file_unavailable"
    default_detail = "This material does not contain a downloadable file."


class MaterialDownloadNotAllowed(CodedAPIException):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "material_download_not_allowed"
    default_detail = "Downloading this material is not allowed."


class LearningMaterialDownloadView(generics.GenericAPIView):
    permission_classes = (MaterialPermission,)
    allow_student_access = True

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    def get(self, request, *args, **kwargs):
        del args, kwargs
        material = get_object_or_404(
            material_queryset_for(request.user),
            pk=self.kwargs["pk"],
        )
        self.check_object_permissions(request, material)
        if not material.download_allowed:
            raise MaterialDownloadNotAllowed()
        if not material.file:
            raise MaterialFileUnavailable()
        return FileResponse(
            material.file.open("rb"),
            as_attachment=True,
            filename=material.original_filename or material.file.name,
            content_type=material.mime_type or "application/octet-stream",
        )


class VideoNotReady(CodedAPIException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "video_not_ready"
    default_detail = "Video is not ready for playback."


class LearningMaterialPlaybackView(generics.GenericAPIView):
    permission_classes = (MaterialPermission,)
    allow_student_access = True

    @extend_schema(responses={(200, "video/*"): OpenApiTypes.BINARY})
    def get(self, request, *args, **kwargs):
        del args, kwargs
        material = get_object_or_404(
            material_queryset_for(request.user),
            pk=self.kwargs["pk"],
            type=LearningMaterialType.VIDEO,
        )
        self.check_object_permissions(request, material)
        if material.video_status != VideoProcessingStatus.READY:
            raise VideoNotReady()
        if not material.file:
            raise MaterialFileUnavailable()
        return FileResponse(
            material.file.open("rb"),
            as_attachment=False,
            filename=material.original_filename or material.file.name,
            content_type=material.mime_type or "video/mp4",
        )


def scorm_queryset_for(user):
    return ScormPackage.objects.select_related(
        "course",
        "lesson",
        "lesson__topic",
        "lesson__topic__module",
    ).filter(course__in=courses_accessible_to(user))


class LessonScormPackageListCreateView(generics.ListCreateAPIView):
    permission_classes = (MaterialPermission,)
    serializer_class = ScormPackageSerializer

    def get_lesson(self):
        lesson = get_object_or_404(
            Lesson.objects.select_related("topic__module__course").filter(
                topic__module__course__in=courses_accessible_to(self.request.user)
            ),
            pk=self.kwargs["lesson_pk"],
        )
        self.check_object_permissions(self.request, lesson)
        return lesson

    def get_queryset(self):
        return scorm_queryset_for(self.request.user).filter(lesson=self.get_lesson())

    def perform_create(self, serializer):
        lesson = self.get_lesson()
        serializer.save(
            lesson=lesson,
            course=lesson.course,
            created_by=self.request.user,
            updated_by=self.request.user,
        )


class ScormPackageDetailView(generics.RetrieveAPIView):
    permission_classes = (MaterialPermission,)
    serializer_class = ScormPackageSerializer

    def get_queryset(self):
        return scorm_queryset_for(self.request.user)


class ScormContentUnavailable(CodedAPIException):
    error_code = "scorm_content_unavailable"
    default_detail = "SCORM package content is unavailable."


@method_decorator(xframe_options_exempt, name="dispatch")
class ScormPackageContentView(generics.GenericAPIView):
    permission_classes = (MaterialPermission,)

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    def get(self, request, *args, **kwargs):
        del args, kwargs
        package = get_object_or_404(
            scorm_queryset_for(request.user),
            pk=self.kwargs["pk"],
        )
        self.check_object_permissions(request, package)
        try:
            content, normalized_path = stream_scorm_member(
                package.file,
                self.kwargs["path"],
            )
        except (BadZipFile, KeyError, OSError, RuntimeError, ValidationError) as exc:
            raise ScormContentUnavailable() from exc
        content_type = mimetypes.guess_type(normalized_path)[0]
        response = StreamingHttpResponse(
            content,
            content_type=content_type or "application/octet-stream",
        )
        frame_ancestors = " ".join(("'self'", *settings.SCORM_FRAME_ANCESTORS))
        response["Content-Security-Policy"] = (
            "sandbox allow-scripts allow-forms; "
            f"frame-ancestors {frame_ancestors}; "
            "default-src 'self' data: blob:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "img-src 'self' data: blob:; media-src 'self' blob:"
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response
