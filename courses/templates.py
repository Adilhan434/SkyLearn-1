from django.db import transaction

from audit.models import CourseHistoryAction, CourseHistoryObjectType
from audit.services import record_course_history_event
from courses.copying import (
    build_course_snapshot,
    course_copy_queryset,
    create_course_from_snapshot,
)
from courses.models import CourseTemplate


@transaction.atomic
def create_course_template(source, title, description, is_active, actor):
    """Persist a consistent snapshot that no longer depends on its source."""

    source = course_copy_queryset().select_for_update().get(pk=source.pk)
    return CourseTemplate.objects.create(
        title=title,
        description=description,
        snapshot=build_course_snapshot(source),
        is_active=is_active,
        created_by=actor,
        updated_by=actor,
    )


@transaction.atomic
def create_course_from_template(template, title, code, actor):
    """Lock an active template and materialize its snapshot as a Draft."""

    template = CourseTemplate.objects.select_for_update().get(
        pk=template.pk,
        is_active=True,
    )
    course = create_course_from_snapshot(template.snapshot, title, code, actor)
    record_course_history_event(
        course=course,
        action=CourseHistoryAction.COURSE_CREATED,
        actor=actor,
        object_type=CourseHistoryObjectType.COURSE,
        object_id=course.pk,
        object_title=course.title,
        details={
            "source": "template",
            "template_id": template.pk,
        },
    )
    return course
