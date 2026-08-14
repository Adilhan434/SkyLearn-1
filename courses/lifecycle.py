from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from api.v1.exceptions import CodedAPIException
from courses.models import (
    Course,
    CourseLifecycleAction,
    CourseStatus,
    CourseStatusHistory,
    CourseTeachingRole,
)


class InvalidCourseTransition(CodedAPIException):
    error_code = "invalid_course_transition"
    default_detail = "This course status transition is not allowed."


class CourseNotReady(CodedAPIException):
    error_code = "course_not_ready"
    default_detail = "Course is not ready for review."


@dataclass(frozen=True)
class TransitionRule:
    sources: tuple[str, ...]
    target: str


TRANSITION_RULES = {
    CourseLifecycleAction.SUBMIT_REVIEW: TransitionRule(
        (CourseStatus.DRAFT, CourseStatus.NEEDS_REVISION),
        CourseStatus.UNDER_REVIEW,
    ),
    CourseLifecycleAction.RETURN_REVISION: TransitionRule(
        (CourseStatus.UNDER_REVIEW,),
        CourseStatus.NEEDS_REVISION,
    ),
    CourseLifecycleAction.PUBLISH: TransitionRule(
        (CourseStatus.UNDER_REVIEW,),
        CourseStatus.PUBLISHED,
    ),
    CourseLifecycleAction.ARCHIVE: TransitionRule(
        (CourseStatus.PUBLISHED,),
        CourseStatus.ARCHIVED,
    ),
    CourseLifecycleAction.RESTORE: TransitionRule(
        (CourseStatus.ARCHIVED,),
        CourseStatus.PUBLISHED,
    ),
}


def review_readiness_errors(course):
    errors = []
    has_primary_teacher = course.teaching_assignments.filter(
        role=CourseTeachingRole.TEACHER,
        is_primary=True,
        user__is_active=True,
    ).exists()
    if not has_primary_teacher:
        errors.append("Course has no active primary teacher.")
    return errors


@transaction.atomic
def transition_course(course, action, actor, comment=""):
    locked_course = Course.objects.select_for_update().get(pk=course.pk)
    rule = TRANSITION_RULES[action]
    if locked_course.status not in rule.sources:
        raise InvalidCourseTransition()

    if action == CourseLifecycleAction.SUBMIT_REVIEW:
        readiness_errors = review_readiness_errors(locked_course)
        if readiness_errors:
            raise CourseNotReady(details=readiness_errors)
        locked_course.review_comment = ""
    elif action == CourseLifecycleAction.RETURN_REVISION:
        locked_course.review_comment = comment
    elif action == CourseLifecycleAction.PUBLISH:
        locked_course.published_at = timezone.now()
        locked_course.published_by = actor

    previous_status = locked_course.status
    locked_course.status = rule.target
    locked_course.updated_by = actor
    update_fields = ["status", "review_comment", "updated_by", "updated_at"]
    if action == CourseLifecycleAction.PUBLISH:
        update_fields.extend(("published_at", "published_by"))
    locked_course.save(
        allow_archived_update=previous_status == CourseStatus.ARCHIVED,
        update_fields=update_fields,
    )
    CourseStatusHistory.objects.create(
        course=locked_course,
        action=action,
        from_status=previous_status,
        to_status=rule.target,
        comment=comment,
        created_by=actor,
        updated_by=actor,
    )
    return locked_course
