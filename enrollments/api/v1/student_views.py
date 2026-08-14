from rest_framework import generics

from enrollments.api.v1.pagination import StudentCoursePagination
from enrollments.api.v1.serializers import StudentCourseSerializer
from enrollments.permissions import StudentCoursePermission
from enrollments.querysets import student_courses_queryset


class StudentCourseListView(generics.ListAPIView):
    serializer_class = StudentCourseSerializer
    permission_classes = (StudentCoursePermission,)
    pagination_class = StudentCoursePagination

    def get_queryset(self):
        return student_courses_queryset(self.request.user)


class StudentCourseDetailView(generics.RetrieveAPIView):
    serializer_class = StudentCourseSerializer
    permission_classes = (StudentCoursePermission,)

    def get_queryset(self):
        return student_courses_queryset(self.request.user)
