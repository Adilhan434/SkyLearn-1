from django.conf import settings
from django.db import models
from django.utils import timezone

from audit.models import AuditModel
from courses.models import Course


class EnrollmentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    WITHDRAWN = "withdrawn", "Withdrawn"
    SUSPENDED = "suspended", "Suspended"


class EnrollmentSource(models.TextChoices):
    MANUAL = "manual", "Manual"
    SIS_SYNC = "sis_sync", "SIS sync"


class SISSyncAction(models.TextChoices):
    ENROLL = "enroll", "Enroll"
    WITHDRAW = "withdraw", "Withdraw"


class SISSyncResult(models.TextChoices):
    CREATED = "created", "Created"
    REACTIVATED = "reactivated", "Reactivated"
    WITHDRAWN = "withdrawn", "Withdrawn"
    UNCHANGED = "unchanged", "Unchanged"


class Enrollment(AuditModel):
    """A student's lifecycle membership in a Release 1 course."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_enrollments",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    status = models.CharField(
        max_length=20,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.ACTIVE,
        db_index=True,
    )
    source = models.CharField(
        max_length=20,
        choices=EnrollmentSource.choices,
        default=EnrollmentSource.MANUAL,
    )
    external_sis_id = models.CharField(max_length=255, blank=True, db_index=True)
    enrolled_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-enrolled_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("student", "course"),
                name="enrollment_unique_student_course",
            ),
        ]
        verbose_name = "Enrollment"
        verbose_name_plural = "Enrollments"

    def __str__(self):
        return f"{self.student} / {self.course.code} ({self.status})"


class SISSyncEvent(models.Model):
    """Durable idempotency record for an external SIS enrollment event."""

    external_event_id = models.CharField(max_length=255, unique=True)
    student_external_id = models.CharField(max_length=30)
    course_code = models.CharField(max_length=50)
    action = models.CharField(max_length=20, choices=SISSyncAction.choices)
    result = models.CharField(max_length=20, choices=SISSyncResult.choices, blank=True)
    enrollment = models.ForeignKey(
        Enrollment,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="sis_sync_events",
    )
    processed_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="sis_sync_events_created",
    )

    class Meta:
        ordering = ("-processed_at", "-id")
        verbose_name = "SIS sync event"
        verbose_name_plural = "SIS sync events"

    def __str__(self):
        return self.external_event_id
