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
