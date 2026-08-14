from django.db import transaction
from django.utils import timezone

from api.v1.exceptions import CodedAPIException
from courses.models import Course
from learning.models import CourseModule, CourseTopic, Lesson


class InvalidStructureOrder(CodedAPIException):
    error_code = "invalid_structure_order"
    default_detail = "Structure order is invalid."


STRUCTURE_MODELS = {
    "module": CourseModule,
    "topic": CourseTopic,
    "lesson": Lesson,
}


def _course_filter(item_type, course):
    if item_type == "module":
        return {"course": course}
    if item_type == "topic":
        return {"module__course": course}
    return {"topic__module__course": course}


def _parent_id(item_type, item):
    if item_type == "module":
        return item.course_id
    if item_type == "topic":
        return item.module_id
    return item.topic_id


def _siblings_queryset(item_type, item):
    if item_type == "module":
        return CourseModule.objects.filter(course_id=item.course_id)
    if item_type == "topic":
        return CourseTopic.objects.filter(module_id=item.module_id)
    return Lesson.objects.filter(topic_id=item.topic_id)


@transaction.atomic
def reorder_structure(course, item_type, items, actor):
    locked_course = Course.objects.select_for_update().get(pk=course.pk)
    model = STRUCTURE_MODELS[item_type]
    item_ids = [item["id"] for item in items]
    objects = list(
        model.objects.select_for_update()
        .filter(pk__in=item_ids, **_course_filter(item_type, locked_course))
        .order_by("pk")
    )
    if len(objects) != len(item_ids):
        raise InvalidStructureOrder(
            "Every item must exist and belong to the selected course."
        )

    parent_ids = {_parent_id(item_type, item) for item in objects}
    if len(parent_ids) != 1:
        raise InvalidStructureOrder("All items must have the same parent.")

    sibling_ids = set(
        _siblings_queryset(item_type, objects[0]).values_list("id", flat=True)
    )
    if sibling_ids != set(item_ids):
        raise InvalidStructureOrder(
            "The complete sibling list is required for reordering."
        )

    by_id = {item.pk: item for item in objects}
    maximum_order = max(item.order for item in objects)
    for index, item in enumerate(objects, start=1):
        item.order = maximum_order + len(objects) + index
    model.objects.bulk_update(objects, ("order",))

    changed_at = timezone.now()
    for item_data in items:
        item = by_id[item_data["id"]]
        item.order = item_data["order"]
        item.updated_by = actor
        item.updated_at = changed_at
    model.objects.bulk_update(
        objects,
        ("order", "updated_by", "updated_at"),
    )
    return locked_course
