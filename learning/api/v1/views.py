from django.db.models import Prefetch
from rest_framework import generics

from courses.models import Course
from courses.permissions import CourseAccessPermission, courses_accessible_to
from learning.models import CourseModule, CourseTopic, Lesson

from .serializers import CourseStructureSerializer


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
