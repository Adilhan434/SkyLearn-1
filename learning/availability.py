from dataclasses import asdict, dataclass

from django.utils import timezone

from learning.models import CourseModule, Lesson, ReleaseType


@dataclass(frozen=True)
class LessonAvailability:
    is_available: bool
    lock_reason: str | None = None

    def as_dict(self):
        return asdict(self)


def _locked(reason):
    return LessonAvailability(is_available=False, lock_reason=reason)


def _previous_module(module):
    return (
        CourseModule.objects.filter(
            course_id=module.course_id,
            order__lt=module.order,
        )
        .order_by("-order", "-id")
        .first()
    )


def _previous_lesson(lesson):
    return (
        Lesson.objects.filter(
            topic_id=lesson.topic_id,
            order__lt=lesson.order,
        )
        .order_by("-order", "-id")
        .first()
    )


def evaluate_lesson_availability(
    lesson,
    *,
    completed_lesson_ids=(),
    at=None,
):
    """Evaluate student-facing release rules without frontend calculations."""

    completed_ids = set(completed_lesson_ids)
    current_time = at or timezone.now()
    module = lesson.topic.module

    if not lesson.is_published:
        return _locked("Lesson is not published.")

    if module.release_type == ReleaseType.DATE:
        if module.release_at is None or module.release_at > current_time:
            return _locked("This module is not available yet.")
    elif module.release_type == ReleaseType.AFTER_PREVIOUS:
        previous_module = _previous_module(module)
        if previous_module is not None:
            previous_lesson_ids = set(
                Lesson.objects.filter(
                    topic__module=previous_module,
                    is_published=True,
                ).values_list("id", flat=True)
            )
            if not previous_lesson_ids.issubset(completed_ids):
                return _locked("Complete the previous module.")

    if lesson.release_type == ReleaseType.DATE:
        if lesson.release_at is None or lesson.release_at > current_time:
            return _locked("This lesson is not available yet.")
    elif lesson.release_type == ReleaseType.AFTER_LESSON:
        if (
            lesson.required_lesson_id is None
            or lesson.required_lesson_id not in completed_ids
        ):
            return _locked("Complete the required lesson.")
    elif lesson.release_type == ReleaseType.AFTER_PREVIOUS:
        previous_lesson = _previous_lesson(lesson)
        if (
            previous_lesson is not None
            and previous_lesson.pk not in completed_ids
        ):
            return _locked("Complete the previous lesson.")

    return LessonAvailability(is_available=True)
