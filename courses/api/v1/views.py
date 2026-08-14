from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics

from courses.models import Course
from courses.permissions import CourseAccessPermission, courses_accessible_to

from .filters import CourseFilter
from .pagination import CoursePagination
from .serializers import CourseDetailSerializer, CourseListSerializer


class CourseListCreateView(generics.ListCreateAPIView):
    permission_classes = (CourseAccessPermission,)
    pagination_class = CoursePagination
    filter_backends = (DjangoFilterBackend, filters.SearchFilter)
    filterset_class = CourseFilter
    search_fields = ("title", "code")

    def get_queryset(self):
        queryset = Course.objects.select_related(
            "semester",
            "faculty",
            "department",
            "program",
        )
        return courses_accessible_to(self.request.user, queryset)

    def get_serializer_class(self):
        if self.request.method == "GET":
            return CourseListSerializer
        return CourseDetailSerializer


class CourseDetailView(generics.RetrieveAPIView):
    serializer_class = CourseDetailSerializer
    permission_classes = (CourseAccessPermission,)

    def get_queryset(self):
        queryset = Course.objects.select_related(
            "semester",
            "faculty",
            "department",
            "program",
            "created_by",
            "updated_by",
        )
        return courses_accessible_to(self.request.user, queryset)
