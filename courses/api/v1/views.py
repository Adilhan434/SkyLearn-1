from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from courses.models import Course

from .filters import CourseFilter
from .pagination import CoursePagination
from .serializers import CourseDetailSerializer, CourseListSerializer


class CourseListCreateView(generics.ListCreateAPIView):
    queryset = Course.objects.select_related(
        "semester",
        "faculty",
        "department",
        "program",
    ).all()
    pagination_class = CoursePagination
    filter_backends = (DjangoFilterBackend, filters.SearchFilter)
    filterset_class = CourseFilter
    search_fields = ("title", "code")

    def get_permissions(self):
        permission_classes = (
            (IsAdminUser,) if self.request.method == "POST" else (IsAuthenticated,)
        )
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return CourseListSerializer
        return CourseDetailSerializer


class CourseDetailView(generics.RetrieveAPIView):
    queryset = Course.objects.select_related(
        "semester",
        "faculty",
        "department",
        "program",
        "created_by",
        "updated_by",
    ).all()
    serializer_class = CourseDetailSerializer
    permission_classes = (IsAuthenticated,)
