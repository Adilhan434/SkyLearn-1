from django.db import models
from django.db.models import F, Q

from audit.models import AuditModel
from courses.models import Course


class CalendarEventType(models.TextChoices):
    COURSE_START = "course_start", "Course start"
    COURSE_END = "course_end", "Course end"
    MODULE_RELEASE = "module_release", "Module release"
    LESSON_RELEASE = "lesson_release", "Lesson release"
    CUSTOM = "custom", "Custom"


class CalendarEvent(AuditModel):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="calendar_events",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=30, choices=CalendarEventType.choices)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(blank=True, null=True)
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ("start_at", "id")
        indexes = [
            models.Index(
                fields=("course", "start_at"),
                name="calendar_course_start_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(end_at__isnull=True) | Q(end_at__gte=F("start_at")),
                name="calendar_end_not_before_start",
            )
        ]
        verbose_name = "Calendar event"
        verbose_name_plural = "Calendar events"

    def __str__(self):
        return f"{self.course.code} / {self.title}"
