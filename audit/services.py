from audit.models import CourseHistoryEvent


def record_course_history_event(
    *,
    course,
    action,
    actor,
    object_type,
    object_id,
    object_title,
    details=None,
):
    """Append one normalized event to a course history."""

    return CourseHistoryEvent.objects.create(
        course=course,
        action=action,
        actor=actor,
        object_type=object_type,
        object_id=object_id,
        object_title=object_title,
        details=details or {},
    )
