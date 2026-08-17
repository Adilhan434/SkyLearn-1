from django.db import IntegrityError, transaction
from django.utils import timezone

from api.v1.exceptions import CodedAPIException
from enrollments.models import Enrollment, EnrollmentStatus


class AlreadyEnrolled(CodedAPIException):
    error_code = "already_enrolled"
    default_detail = "The student is already enrolled in this course."


@transaction.atomic
def enroll_student(course, student, source, external_sis_id, actor):
    """Create or reactivate the single lifecycle row for a student/course."""

    enrollment = (
        Enrollment.objects.select_for_update()
        .filter(student=student, course=course)
        .first()
    )
    if enrollment is not None:
        if enrollment.status == EnrollmentStatus.ACTIVE:
            raise AlreadyEnrolled()
        enrollment.status = EnrollmentStatus.ACTIVE
        enrollment.source = source
        enrollment.external_sis_id = external_sis_id
        enrollment.enrolled_at = timezone.now()
        enrollment.updated_by = actor
        enrollment.save(
            update_fields=(
                "status",
                "source",
                "external_sis_id",
                "enrolled_at",
                "updated_by",
                "updated_at",
            )
        )
        return enrollment, False

    try:
        with transaction.atomic():
            enrollment = Enrollment.objects.create(
                student=student,
                course=course,
                status=EnrollmentStatus.ACTIVE,
                source=source,
                external_sis_id=external_sis_id,
                created_by=actor,
                updated_by=actor,
            )
    except IntegrityError as exc:
        raise AlreadyEnrolled() from exc
    return enrollment, True
