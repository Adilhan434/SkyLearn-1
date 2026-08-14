from rest_framework import generics

from enrollments.api.v1.pagination import StudentCoursePagination
from enrollments.api.v1.serializers import (
    StudentCourseDetailSerializer,
    StudentCourseSerializer,
)
from enrollments.permissions import StudentCoursePermission
from enrollments.querysets import (
    student_course_detail_queryset,
    student_courses_queryset,
)
from progress.models import LessonProgress, LessonProgressStatus


class StudentCourseListView(generics.ListAPIView):
    serializer_class = StudentCourseSerializer
    permission_classes = (StudentCoursePermission,)
    pagination_class = StudentCoursePagination

    def get_queryset(self):
        return student_courses_queryset(self.request.user)


class StudentCourseDetailView(generics.RetrieveAPIView):
    serializer_class = StudentCourseDetailSerializer
    permission_classes = (StudentCoursePermission,)

    def get_queryset(self):
        return student_course_detail_queryset(self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        course_id = self.kwargs.get("pk")
        user = self.request.user
        if not course_id or not user.is_authenticated:
            return context
        progress_items = LessonProgress.objects.filter(
            student=user,
            lesson__topic__module__course_id=course_id,
        )
        context["lesson_progress_by_id"] = {
            item.lesson_id: item for item in progress_items
        }
        context["completed_lesson_ids"] = {
            item.lesson_id
            for item in progress_items
            if item.status == LessonProgressStatus.COMPLETED
        }
        return context
