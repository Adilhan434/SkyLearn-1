from courses.models import Course, CourseStatus
from courses.permissions import courses_accessible_to
from enrollments.models import EnrollmentStatus

from calendar_events.models import CalendarEvent


def staff_calendar_events(user):
    return CalendarEvent.objects.select_related("course", "created_by").filter(
        course__in=courses_accessible_to(user)
    )


def student_calendar_events(user):
    student_courses = Course.objects.filter(
        status=CourseStatus.PUBLISHED,
        enrollments__student=user,
        enrollments__status=EnrollmentStatus.ACTIVE,
    )
    return CalendarEvent.objects.select_related("course").filter(
        course__in=student_courses,
        is_public=True,
    )
