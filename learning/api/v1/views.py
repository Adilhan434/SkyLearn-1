from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response

from api.v1.exceptions import CodedAPIException
from courses.models import Course
from courses.permissions import CourseAccessPermission, courses_accessible_to
from learning.models import CourseModule, CourseTopic, Lesson, ReleaseType
from learning.permissions import (
    StructureManagePermission,
    StructureObjectPermission,
)

from .serializers import (
    CourseModuleWriteSerializer,
    CourseStructureSerializer,
    CourseTopicWriteSerializer,
    DeleteConfirmationSerializer,
    LessonWriteSerializer,
)


class StructureNotEmpty(CodedAPIException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "structure_not_empty"
    default_detail = "Structure contains nested objects. Confirm cascade deletion."


class LessonIsRequired(CodedAPIException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "lesson_is_required"
    default_detail = "Lesson is required by another lesson."


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
    return Course.objects.prefetch_related(
        Prefetch("modules", queryset=modules)
    )


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
        has_external_dependents = Lesson.objects.filter(
            required_lesson__in=module_lessons
        ).exclude(topic__module=instance).exists()
        if has_external_dependents:
            raise StructureNotEmpty(
                "Module lessons are prerequisites for lessons outside the module."
            )
        module_lessons.filter(required_lesson__isnull=False).update(
            required_lesson=None,
            release_type=ReleaseType.ALWAYS,
            release_at=None,
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
        has_external_dependents = Lesson.objects.filter(
            required_lesson__in=topic_lessons
        ).exclude(topic=instance).exists()
        if has_external_dependents:
            raise StructureNotEmpty(
                "Topic lessons are prerequisites for lessons outside the topic."
            )
        topic_lessons.filter(required_lesson__isnull=False).update(
            required_lesson=None,
            release_type=ReleaseType.ALWAYS,
            release_at=None,
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

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.dependent_lessons.exists():
            raise LessonIsRequired()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
