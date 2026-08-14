from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers
from rest_framework import filters, generics

from accounts.models import RoleCode
from courses.models import (
    Course,
    CourseStatus,
    CourseTeachingAssignment,
    CourseTeachingRole,
)
from courses.permissions import (
    CourseAccessPermission,
    courses_accessible_to,
    has_global_course_access,
)

from .filters import CourseFilter
from .pagination import CoursePagination
from .serializers import (
    CourseDetailSerializer,
    CourseListSerializer,
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
    filter_backends = (DjangoFilterBackend, filters.SearchFilter)
    filterset_class = CourseFilter
    search_fields = ("title", "code")

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
            and course.status != CourseStatus.DRAFT
        ):
            raise serializers.ValidationError(
                {"status": "Teachers can edit only draft courses."}
            )
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != CourseStatus.DRAFT:
            raise serializers.ValidationError(
                {"status": "Only draft courses can be permanently deleted."}
            )
        instance.delete()
