from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework import filters, generics
from rest_framework.response import Response

from accounts.models import LMSPermissionCode, RoleCode
from audit.models import CourseHistoryEvent
from courses.copying import copy_course, course_copy_queryset
from courses.lifecycle import transition_course
from courses.models import (
    Course,
    CourseLifecycleAction,
    CourseStatus,
    CourseTeachingAssignment,
    CourseTeachingRole,
)
from courses.permissions import (
    CourseAccessPermission,
    CourseLifecyclePermission,
    courses_accessible_to,
    has_global_course_access,
)
from courses.readiness import evaluate_course_readiness

from .filters import CourseFilter, CourseSearchFilter
from .pagination import CoursePagination
from .serializers import (
    CourseDetailSerializer,
    CourseCopySerializer,
    CourseHistoryEventSerializer,
    CourseListSerializer,
    CourseReadinessSerializer,
    ReturnForRevisionSerializer,
    CourseWriteSerializer,
)


def course_read_queryset():
    primary_teachers = CourseTeachingAssignment.objects.filter(
        role=CourseTeachingRole.TEACHER,
        is_primary=True,
    ).select_related("user")
    return Course.objects.select_related(
        "semester",
        "faculty",
        "department",
        "program",
        "group",
    ).prefetch_related(
        Prefetch(
            "teaching_assignments",
            queryset=primary_teachers,
            to_attr="primary_teacher_assignments",
        )
    )


class CourseListCreateView(generics.ListCreateAPIView):
    permission_classes = (CourseAccessPermission,)
    pagination_class = CoursePagination
    filter_backends = (
        DjangoFilterBackend,
        CourseSearchFilter,
        filters.OrderingFilter,
    )
    filterset_class = CourseFilter
    search_fields = (
        "title",
        "code",
        "description",
        "teaching_assignments__user__first_name",
        "teaching_assignments__user__last_name",
    )
    ordering_fields = (
        "title",
        "code",
        "created_at",
        "updated_at",
        "start_date",
        "end_date",
        "status",
    )
    ordering = ("code",)

    def get_queryset(self):
        return courses_accessible_to(self.request.user, course_read_queryset())

    def get_serializer_class(self):
        if self.request.method == "GET":
            return CourseListSerializer
        return CourseWriteSerializer


class CourseDetailView(generics.RetrieveUpdateDestroyAPIView):
    http_method_names = ("get", "patch", "delete", "head", "options")
    serializer_class = CourseDetailSerializer
    permission_classes = (CourseAccessPermission,)

    def get_queryset(self):
        queryset = course_read_queryset().select_related(
            "created_by",
            "updated_by",
            "published_by",
        )
        return courses_accessible_to(self.request.user, queryset)

    def get_serializer_class(self):
        if self.request.method == "GET":
            return CourseDetailSerializer
        return CourseWriteSerializer

    def perform_update(self, serializer):
        course = self.get_object()
        user = self.request.user
        if course.status == CourseStatus.ARCHIVED:
            raise serializers.ValidationError(
                {"status": "Archived courses cannot be edited."}
            )
        is_teacher = user.roles.filter(code=RoleCode.TEACHER).exists()
        if (
            is_teacher
            and not has_global_course_access(user)
            and course.status
            not in {CourseStatus.DRAFT, CourseStatus.NEEDS_REVISION}
        ):
            raise serializers.ValidationError(
                {
                    "status": (
                        "Teachers can edit only draft or needs-revision courses."
                    )
                }
            )
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != CourseStatus.DRAFT:
            raise serializers.ValidationError(
                {"status": "Only draft courses can be permanently deleted."}
            )
        instance.delete()


class CourseLifecycleView(generics.GenericAPIView):
    permission_classes = (CourseLifecyclePermission,)
    serializer_class = CourseDetailSerializer
    action = None
    required_permission = None

    def get_queryset(self):
        return courses_accessible_to(self.request.user, course_read_queryset())

    def post(self, request, *args, **kwargs):
        course = self.get_object()
        comment = ""
        if self.action == CourseLifecycleAction.RETURN_REVISION:
            input_serializer = ReturnForRevisionSerializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)
            comment = input_serializer.validated_data["comment"]
        course = transition_course(course, self.action, request.user, comment)
        return Response(CourseDetailSerializer(course).data)


class CourseReadinessView(generics.GenericAPIView):
    permission_classes = (CourseAccessPermission,)
    serializer_class = CourseReadinessSerializer

    def get_queryset(self):
        return courses_accessible_to(self.request.user, course_read_queryset())

    @extend_schema(responses=CourseReadinessSerializer)
    def get(self, request, *args, **kwargs):
        del request, args, kwargs
        course = self.get_object()
        return Response(evaluate_course_readiness(course))


class CourseHistoryView(generics.ListAPIView):
    queryset = CourseHistoryEvent.objects.none()
    serializer_class = CourseHistoryEventSerializer
    permission_classes = (CourseAccessPermission,)
    pagination_class = CoursePagination

    def get_course(self):
        if not hasattr(self, "_course"):
            self._course = get_object_or_404(
                courses_accessible_to(self.request.user),
                pk=self.kwargs["pk"],
            )
            self.check_object_permissions(self.request, self._course)
        return self._course

    def get_queryset(self):
        return CourseHistoryEvent.objects.filter(
            course=self.get_course(),
        ).select_related("actor")


class CourseCopyView(generics.GenericAPIView):
    permission_classes = (CourseLifecyclePermission,)
    serializer_class = CourseCopySerializer
    required_permission = LMSPermissionCode.COURSES_COPY

    def get_queryset(self):
        return courses_accessible_to(self.request.user, course_copy_queryset())

    @extend_schema(
        request=CourseCopySerializer,
        responses={201: CourseDetailSerializer},
    )
    def post(self, request, *args, **kwargs):
        del args, kwargs
        source = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        copied_course = copy_course(
            source,
            serializer.validated_data["title"],
            serializer.validated_data["code"],
            request.user,
        )
        return Response(
            CourseDetailSerializer(copied_course).data,
            status=201,
        )


class SubmitReviewView(CourseLifecycleView):
    action = CourseLifecycleAction.SUBMIT_REVIEW
    required_permission = LMSPermissionCode.COURSES_SUBMIT_REVIEW

    @extend_schema(request=None, responses=CourseDetailSerializer)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class ReturnForRevisionView(CourseLifecycleView):
    action = CourseLifecycleAction.RETURN_REVISION
    required_permission = LMSPermissionCode.COURSES_REVIEW

    @extend_schema(
        request=ReturnForRevisionSerializer,
        responses=CourseDetailSerializer,
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class PublishCourseView(CourseLifecycleView):
    action = CourseLifecycleAction.PUBLISH
    required_permission = LMSPermissionCode.COURSES_PUBLISH

    @extend_schema(request=None, responses=CourseDetailSerializer)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class ArchiveCourseView(CourseLifecycleView):
    action = CourseLifecycleAction.ARCHIVE
    required_permission = LMSPermissionCode.COURSES_ARCHIVE

    @extend_schema(request=None, responses=CourseDetailSerializer)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class RestoreCourseView(CourseLifecycleView):
    action = CourseLifecycleAction.RESTORE
    required_permission = LMSPermissionCode.COURSES_ARCHIVE

    @extend_schema(request=None, responses=CourseDetailSerializer)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
