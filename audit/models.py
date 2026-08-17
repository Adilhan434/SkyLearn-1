from django.conf import settings
from django.db import models


class AuditModel(models.Model):
    """Shared ownership and timestamp fields for new Release 1 models."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_updated",
    )

    class Meta:
        abstract = True


class CourseHistoryAction(models.TextChoices):
    COURSE_CREATED = "course_created", "Course created"
    COURSE_UPDATED = "course_updated", "Course updated"
    MODULE_CREATED = "module_created", "Module created"
    MODULE_UPDATED = "module_updated", "Module updated"
    MODULE_DELETED = "module_deleted", "Module deleted"
    TOPIC_CREATED = "topic_created", "Topic created"
    TOPIC_UPDATED = "topic_updated", "Topic updated"
    TOPIC_DELETED = "topic_deleted", "Topic deleted"
    LESSON_CREATED = "lesson_created", "Lesson created"
    LESSON_UPDATED = "lesson_updated", "Lesson updated"
    LESSON_DELETED = "lesson_deleted", "Lesson deleted"
    MATERIAL_UPLOADED = "material_uploaded", "Material uploaded"
    MATERIAL_DELETED = "material_deleted", "Material deleted"
    SUBMITTED_FOR_REVIEW = "submitted_for_review", "Submitted for review"
    RETURNED_FOR_REVISION = "returned_for_revision", "Returned for revision"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"
    RESTORED = "restored", "Restored"
    COPIED = "copied", "Copied"


class CourseHistoryObjectType(models.TextChoices):
    COURSE = "course", "Course"
    MODULE = "module", "Module"
    TOPIC = "topic", "Topic"
    LESSON = "lesson", "Lesson"
    MATERIAL = "material", "Material"


class CourseHistoryEvent(models.Model):
    """Append-only course-scoped event used by the Release 1 history API."""

    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="history_events",
    )
    action = models.CharField(max_length=40, choices=CourseHistoryAction.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="course_history_events",
    )
    object_type = models.CharField(
        max_length=20,
        choices=CourseHistoryObjectType.choices,
    )
    object_id = models.PositiveBigIntegerField()
    object_title = models.CharField(max_length=255)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("course", "created_at"),
                name="audit_history_course_time_idx",
            )
        ]
        verbose_name = "Course history event"
        verbose_name_plural = "Course history events"

    def __str__(self):
        return (
            f"{self.course.code}: {self.action} ({self.object_type}:{self.object_id})"
        )
