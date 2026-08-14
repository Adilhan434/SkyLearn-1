from django.db.models import Prefetch

from courses.models import (
    Course,
    CourseStatus,
    CourseTeachingAssignment,
    CourseTeachingRole,
)
from enrollments.models import EnrollmentStatus
from learning.models import CourseModule, CourseTopic, Lesson


def student_courses_queryset(user):
    """Published courses with an active enrollment for the given student."""

    primary_teachers = CourseTeachingAssignment.objects.filter(
        role=CourseTeachingRole.TEACHER,
        is_primary=True,
    ).select_related("user")
    return (
        Course.objects.filter(
            status=CourseStatus.PUBLISHED,
            enrollments__student=user,
            enrollments__status=EnrollmentStatus.ACTIVE,
        )
        .select_related("semester", "faculty", "department", "program")
        .prefetch_related(
            Prefetch(
                "teaching_assignments",
                queryset=primary_teachers,
                to_attr="primary_teacher_assignments",
            )
        )
        .order_by("code")
        .distinct()
    )


def student_course_detail_queryset(user):
    """Student courses with their published learning structure prefetched."""

    published_lessons = Lesson.objects.filter(is_published=True).prefetch_related(
        "materials"
    )
    topics = CourseTopic.objects.prefetch_related(
        Prefetch("lessons", queryset=published_lessons),
    )
    modules = CourseModule.objects.prefetch_related(
        Prefetch("topics", queryset=topics),
    )
    return student_courses_queryset(user).prefetch_related(
        Prefetch("modules", queryset=modules),
    )
