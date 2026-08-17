from django.conf import settings
from django.db import models
from django.db.models import F, Q

from learning.models import Lesson


class LessonProgressStatus(models.TextChoices):
    NOT_STARTED = "not_started", "Not started"
    IN_PROGRESS = "in_progress", "In progress"
    COMPLETED = "completed", "Completed"


class LessonProgress(models.Model):
    """Minimal operational progress for one student and one lesson."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lesson_progress",
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="student_progress",
    )
    status = models.CharField(
        max_length=20,
        choices=LessonProgressStatus.choices,
        default=LessonProgressStatus.NOT_STARTED,
        db_index=True,
    )
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("student", "lesson"),
                name="progress_unique_student_lesson",
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        status=LessonProgressStatus.NOT_STARTED,
                        started_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status=LessonProgressStatus.IN_PROGRESS,
                        started_at__isnull=False,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status=LessonProgressStatus.COMPLETED,
                        started_at__isnull=False,
                        completed_at__isnull=False,
                    )
                ),
                name="progress_status_timestamps_consistent",
            ),
            models.CheckConstraint(
                check=Q(completed_at__isnull=True)
                | Q(completed_at__gte=F("started_at")),
                name="progress_completion_not_before_start",
            ),
        ]
        verbose_name = "Lesson progress"
        verbose_name_plural = "Lesson progress"

    def __str__(self):
        return f"{self.student} / lesson {self.lesson_id} ({self.status})"
