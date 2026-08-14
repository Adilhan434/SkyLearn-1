from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status

from api.v1.exceptions import CodedAPIException
from courses.models import Course, CourseStatus
from enrollments.models import EnrollmentStatus
from learning.availability import evaluate_lesson_availability
from learning.models import CourseModule, CourseTopic, Lesson
from progress.models import LessonProgress, LessonProgressStatus


class StudentLessonNotFound(CodedAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "student_lesson_not_found"
    default_detail = "The lesson is not available to this student."


class StudentCourseNotFound(CodedAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "student_course_not_found"
    default_detail = "The course is not available to this student."


class LessonLocked(CodedAPIException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "lesson_locked"
    default_detail = "The lesson is locked."


def _student_course_queryset(student):
    published_lessons = Lesson.objects.filter(is_published=True)
    topics = CourseTopic.objects.prefetch_related(
        Prefetch("lessons", queryset=published_lessons),
    )
    modules = CourseModule.objects.prefetch_related(
        Prefetch("topics", queryset=topics),
    )
    return (
        Course.objects.filter(
            status=CourseStatus.PUBLISHED,
            enrollments__student=student,
            enrollments__status=EnrollmentStatus.ACTIVE,
        )
        .prefetch_related(Prefetch("modules", queryset=modules))
        .distinct()
    )


def _course_lessons(course):
    return [
        lesson
        for module in course.modules.all()
        for topic in module.topics.all()
        for lesson in topic.lessons.all()
    ]


def calculate_course_progress(course, completed_lesson_ids=()):
    """Calculate operational progress from a prefetched course hierarchy."""

    lessons = _course_lessons(course)
    completed_ids = set(completed_lesson_ids)
    available_ids = {
        lesson.pk
        for lesson in lessons
        if evaluate_lesson_availability(
            lesson,
            completed_lesson_ids=completed_ids,
        ).is_available
    }
    completed_lessons = len(available_ids & completed_ids)
    total_lessons = len(available_ids)
    progress_percent = (
        round(completed_lessons / total_lessons * 100) if total_lessons else 0
    )
    return {
        "course_id": course.pk,
        "total_lessons": total_lessons,
        "completed_lessons": completed_lessons,
        "progress_percent": progress_percent,
    }


class LessonProgressService:
    @staticmethod
    def _lesson_for_student(student, lesson_id):
        try:
            return (
                Lesson.objects.select_related("topic__module__course")
                .filter(
                    pk=lesson_id,
                    is_published=True,
                    topic__module__course__status=CourseStatus.PUBLISHED,
                    topic__module__course__enrollments__student=student,
                    topic__module__course__enrollments__status=(
                        EnrollmentStatus.ACTIVE
                    ),
                )
                .distinct()
                .get()
            )
        except Lesson.DoesNotExist as exc:
            raise StudentLessonNotFound() from exc

    @staticmethod
    def _completed_lesson_ids(student, course):
        return set(
            LessonProgress.objects.filter(
                student=student,
                lesson__topic__module__course=course,
                status=LessonProgressStatus.COMPLETED,
            ).values_list("lesson_id", flat=True)
        )

    @classmethod
    def _assert_available(cls, student, lesson):
        availability = evaluate_lesson_availability(
            lesson,
            completed_lesson_ids=cls._completed_lesson_ids(
                student,
                lesson.course,
            ),
        )
        if not availability.is_available:
            raise LessonLocked(details={"lock_reason": availability.lock_reason})

    @classmethod
    @transaction.atomic
    def start_lesson(cls, *, student, lesson_id):
        lesson = cls._lesson_for_student(student, lesson_id)
        progress = (
            LessonProgress.objects.select_for_update()
            .filter(student=student, lesson=lesson)
            .first()
        )
        if progress and progress.status == LessonProgressStatus.COMPLETED:
            return progress, False
        cls._assert_available(student, lesson)
        if progress is None:
            (
                progress,
                created,
            ) = LessonProgress.objects.select_for_update().get_or_create(
                student=student,
                lesson=lesson,
                defaults={
                    "status": LessonProgressStatus.IN_PROGRESS,
                    "started_at": timezone.now(),
                },
            )
            if created:
                return progress, True
        if progress.status == LessonProgressStatus.NOT_STARTED:
            progress.status = LessonProgressStatus.IN_PROGRESS
            progress.started_at = timezone.now()
            progress.save(update_fields=("status", "started_at", "updated_at"))
        return progress, False

    @classmethod
    @transaction.atomic
    def complete_lesson(cls, *, student, lesson_id):
        lesson = cls._lesson_for_student(student, lesson_id)
        progress = (
            LessonProgress.objects.select_for_update()
            .filter(student=student, lesson=lesson)
            .first()
        )
        if progress and progress.status == LessonProgressStatus.COMPLETED:
            return progress, False
        cls._assert_available(student, lesson)
        completed_at = timezone.now()
        if progress is None:
            (
                progress,
                created,
            ) = LessonProgress.objects.select_for_update().get_or_create(
                student=student,
                lesson=lesson,
                defaults={
                    "status": LessonProgressStatus.COMPLETED,
                    "started_at": completed_at,
                    "completed_at": completed_at,
                },
            )
            if created:
                return progress, True
            if progress.status == LessonProgressStatus.COMPLETED:
                return progress, False
        progress.status = LessonProgressStatus.COMPLETED
        progress.started_at = progress.started_at or completed_at
        progress.completed_at = completed_at
        progress.save(
            update_fields=(
                "status",
                "started_at",
                "completed_at",
                "updated_at",
            )
        )
        return progress, False


class CourseProgressService:
    @staticmethod
    def _summary(student, course):
        lessons = _course_lessons(course)
        completed_ids = set(
            LessonProgress.objects.filter(
                student=student,
                lesson__in=lessons,
                status=LessonProgressStatus.COMPLETED,
            ).values_list("lesson_id", flat=True)
        )
        return calculate_course_progress(course, completed_ids)

    @classmethod
    def course_summary(cls, *, student, course_id):
        try:
            course = _student_course_queryset(student).get(pk=course_id)
        except Course.DoesNotExist as exc:
            raise StudentCourseNotFound() from exc
        return cls._summary(student, course)

    @classmethod
    def student_summary(cls, *, student):
        courses = [
            cls._summary(student, course)
            for course in _student_course_queryset(student).order_by("code")
        ]
        total_lessons = sum(item["total_lessons"] for item in courses)
        completed_lessons = sum(item["completed_lessons"] for item in courses)
        progress_percent = (
            round(completed_lessons / total_lessons * 100) if total_lessons else 0
        )
        return {
            "total_courses": len(courses),
            "total_lessons": total_lessons,
            "completed_lessons": completed_lessons,
            "progress_percent": progress_percent,
            "courses": courses,
        }
