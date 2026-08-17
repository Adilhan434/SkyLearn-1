from django.db import IntegrityError, transaction
from rest_framework import status

from accounts.models import RoleCode, Student
from api.v1.exceptions import CodedAPIException
from courses.models import Course
from enrollments.models import (
    Enrollment,
    EnrollmentSource,
    EnrollmentStatus,
    SISSyncAction,
    SISSyncEvent,
    SISSyncResult,
)
from enrollments.services import AlreadyEnrolled, enroll_student


class SISEventConflict(CodedAPIException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "sis_event_conflict"
    default_detail = "The SIS event ID was already used with another payload."


class SISStudentNotFound(CodedAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "sis_student_not_found"
    default_detail = "The SIS student was not found."


class SISCourseNotFound(CodedAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "sis_course_not_found"
    default_detail = "The SIS course was not found."


class EnrollmentNotFound(CodedAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "enrollment_not_found"
    default_detail = "The enrollment was not found."


class SISIntegrationService:
    """Apply durable, idempotent SIS enrollment lifecycle events."""

    @staticmethod
    def _same_payload(event, student_external_id, course_code, action):
        return (
            event.student_external_id == student_external_id
            and event.course_code.casefold() == course_code.casefold()
            and event.action == action
        )

    @classmethod
    def _claim_event(
        cls,
        external_event_id,
        student_external_id,
        course_code,
        action,
        actor,
    ):
        try:
            with transaction.atomic():
                event = SISSyncEvent.objects.create(
                    external_event_id=external_event_id,
                    student_external_id=student_external_id,
                    course_code=course_code,
                    action=action,
                    created_by=actor,
                )
            return event, True
        except IntegrityError:
            event = SISSyncEvent.objects.select_for_update().get(
                external_event_id=external_event_id
            )
            if not cls._same_payload(
                event,
                student_external_id,
                course_code,
                action,
            ):
                raise SISEventConflict()
            return event, False

    @staticmethod
    def _resolve_student(student_external_id):
        try:
            profile = Student.objects.select_related("student").get(
                id_number=student_external_id,
                student__is_active=True,
            )
        except Student.DoesNotExist as exc:
            raise SISStudentNotFound() from exc
        if not profile.student.roles.filter(code=RoleCode.STUDENT).exists():
            raise SISStudentNotFound()
        return profile.student

    @staticmethod
    def _resolve_course(course_code):
        try:
            return Course.objects.get(code__iexact=course_code)
        except Course.DoesNotExist as exc:
            raise SISCourseNotFound() from exc

    @staticmethod
    def _enroll(course, student, external_event_id, actor):
        try:
            enrollment, created = enroll_student(
                course=course,
                student=student,
                source=EnrollmentSource.SIS_SYNC,
                external_sis_id=external_event_id,
                actor=actor,
            )
        except AlreadyEnrolled:
            enrollment = Enrollment.objects.select_for_update().get(
                course=course,
                student=student,
            )
            enrollment.source = EnrollmentSource.SIS_SYNC
            enrollment.external_sis_id = external_event_id
            enrollment.updated_by = actor
            enrollment.save(
                update_fields=(
                    "source",
                    "external_sis_id",
                    "updated_by",
                    "updated_at",
                )
            )
            return enrollment, SISSyncResult.UNCHANGED
        return enrollment, (
            SISSyncResult.CREATED if created else SISSyncResult.REACTIVATED
        )

    @staticmethod
    def _withdraw(course, student, actor):
        try:
            enrollment = Enrollment.objects.select_for_update().get(
                course=course,
                student=student,
            )
        except Enrollment.DoesNotExist as exc:
            raise EnrollmentNotFound() from exc
        if enrollment.status == EnrollmentStatus.WITHDRAWN:
            return enrollment, SISSyncResult.UNCHANGED
        enrollment.status = EnrollmentStatus.WITHDRAWN
        enrollment.updated_by = actor
        enrollment.save(update_fields=("status", "updated_by", "updated_at"))
        return enrollment, SISSyncResult.WITHDRAWN

    @classmethod
    @transaction.atomic
    def sync_enrollment(
        cls,
        *,
        external_event_id,
        student_external_id,
        course_code,
        action,
        actor,
    ):
        event, claimed = cls._claim_event(
            external_event_id,
            student_external_id,
            course_code,
            action,
            actor,
        )
        if not claimed:
            return event, False

        student = cls._resolve_student(student_external_id)
        course = cls._resolve_course(course_code)
        if action == SISSyncAction.ENROLL:
            enrollment, result = cls._enroll(
                course,
                student,
                external_event_id,
                actor,
            )
        else:
            enrollment, result = cls._withdraw(course, student, actor)
        event.enrollment = enrollment
        event.result = result
        event.course_code = course.code
        event.save(update_fields=("enrollment", "result", "course_code"))
        return event, True
