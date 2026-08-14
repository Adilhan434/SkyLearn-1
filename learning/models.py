from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from audit.models import AuditModel
from courses.models import Course
from learning.storage import material_storage


class ReleaseType(models.TextChoices):
    ALWAYS = "always", "Always"
    AFTER_PREVIOUS = "after_previous", "After previous"
    AFTER_LESSON = "after_lesson", "After lesson"
    DATE = "date", "Date"


class LessonType(models.TextChoices):
    TEXT = "text", "Text"
    VIDEO = "video", "Video"
    MATERIAL = "material", "Material"
    MIXED = "mixed", "Mixed"
    EXTERNAL_LINK = "external_link", "External link"


class LearningMaterialType(models.TextChoices):
    PDF = "pdf", "PDF"
    DOC = "doc", "DOC"
    DOCX = "docx", "DOCX"
    PPT = "ppt", "PPT"
    PPTX = "pptx", "PPTX"
    IMAGE = "image", "Image"
    AUDIO = "audio", "Audio"
    VIDEO = "video", "Video"
    EXTERNAL_LINK = "external_link", "External link"
    LIBRARY_LINK = "library_link", "Library link"
    OTHER = "other", "Other"


class VideoProcessingStatus(models.TextChoices):
    UPLOADED = "uploaded", "Uploaded"
    PROCESSING = "processing", "Processing"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"


class CourseModule(AuditModel):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="modules",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    release_type = models.CharField(
        max_length=20,
        choices=(
            (ReleaseType.ALWAYS, ReleaseType.ALWAYS.label),
            (ReleaseType.AFTER_PREVIOUS, ReleaseType.AFTER_PREVIOUS.label),
            (ReleaseType.DATE, ReleaseType.DATE.label),
        ),
        default=ReleaseType.ALWAYS,
    )
    release_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("course", "order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("course", "order"),
                name="learning_unique_module_order",
            ),
            models.CheckConstraint(
                check=Q(order__gte=1),
                name="learning_module_order_gte_1",
            ),
            models.CheckConstraint(
                check=(
                    Q(release_type=ReleaseType.DATE, release_at__isnull=False)
                    | (~Q(release_type=ReleaseType.DATE) & Q(release_at__isnull=True))
                ),
                name="learning_module_release_fields",
            ),
        ]
        verbose_name = "Course module"
        verbose_name_plural = "Course modules"

    def clean(self):
        super().clean()
        if self.release_type == ReleaseType.DATE and self.release_at is None:
            raise ValidationError(
                {"release_at": "A date-based module requires release_at."}
            )
        if self.release_type != ReleaseType.DATE and self.release_at is not None:
            raise ValidationError(
                {"release_at": "release_at is allowed only for date release."}
            )

    def __str__(self):
        return f"{self.course.code} / {self.order}. {self.title}"


class CourseTopic(AuditModel):
    module = models.ForeignKey(
        CourseModule,
        on_delete=models.CASCADE,
        related_name="topics",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ("module", "order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("module", "order"),
                name="learning_unique_topic_order",
            ),
            models.CheckConstraint(
                check=Q(order__gte=1),
                name="learning_topic_order_gte_1",
            ),
        ]
        verbose_name = "Course topic"
        verbose_name_plural = "Course topics"

    def __str__(self):
        return f"{self.module} / {self.order}. {self.title}"


class Lesson(AuditModel):
    topic = models.ForeignKey(
        CourseTopic,
        on_delete=models.CASCADE,
        related_name="lessons",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    lesson_type = models.CharField(
        max_length=20,
        choices=LessonType.choices,
        default=LessonType.TEXT,
    )
    content = models.TextField(blank=True)
    estimated_duration_minutes = models.PositiveIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
    )
    order = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    release_type = models.CharField(
        max_length=20,
        choices=ReleaseType.choices,
        default=ReleaseType.ALWAYS,
    )
    release_at = models.DateTimeField(blank=True, null=True)
    required_lesson = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="dependent_lessons",
    )
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ("topic", "order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("topic", "order"),
                name="learning_unique_lesson_order",
            ),
            models.CheckConstraint(
                check=Q(order__gte=1),
                name="learning_lesson_order_gte_1",
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        release_type=ReleaseType.DATE,
                        release_at__isnull=False,
                        required_lesson__isnull=True,
                    )
                    | Q(
                        release_type=ReleaseType.AFTER_LESSON,
                        release_at__isnull=True,
                        required_lesson__isnull=False,
                    )
                    | (
                        Q(
                            release_type__in=(
                                ReleaseType.ALWAYS,
                                ReleaseType.AFTER_PREVIOUS,
                            )
                        )
                        & Q(release_at__isnull=True)
                        & Q(required_lesson__isnull=True)
                    )
                ),
                name="learning_lesson_release_fields",
            ),
        ]
        verbose_name = "Lesson"
        verbose_name_plural = "Lessons"

    @property
    def course(self):
        return self.topic.module.course

    def clean(self):
        super().clean()
        errors = {}
        if self.release_type == ReleaseType.DATE:
            if self.release_at is None:
                errors["release_at"] = "A date-based lesson requires release_at."
            if self.required_lesson_id:
                errors[
                    "required_lesson"
                ] = "A date-based lesson cannot require another lesson."
        elif self.release_type == ReleaseType.AFTER_LESSON:
            if not self.required_lesson_id:
                errors[
                    "required_lesson"
                ] = "An after-lesson release requires required_lesson."
            if self.release_at is not None:
                errors[
                    "release_at"
                ] = "An after-lesson release cannot define release_at."
        elif self.release_at is not None or self.required_lesson_id:
            errors[
                "release_type"
            ] = "Release fields do not match the selected release type."

        if self.required_lesson_id:
            self._validate_required_lesson(errors)
        if errors:
            raise ValidationError(errors)

    def _validate_required_lesson(self, errors):
        required_lesson = self.required_lesson
        if required_lesson is self or (self.pk and required_lesson.pk == self.pk):
            errors["required_lesson"] = "A lesson cannot require itself."
            return
        if required_lesson.course.pk != self.course.pk:
            errors[
                "required_lesson"
            ] = "The required lesson must belong to the same course."
            return

        visited = set()
        current = required_lesson
        while current is not None:
            if current is self or (self.pk and current.pk == self.pk):
                errors[
                    "required_lesson"
                ] = "The required lesson would create a dependency cycle."
                return
            if current.pk in visited:
                errors[
                    "required_lesson"
                ] = "The required lesson chain already contains a cycle."
                return
            visited.add(current.pk)
            current = current.required_lesson

    def __str__(self):
        return f"{self.topic} / {self.order}. {self.title}"


class LearningMaterial(AuditModel):
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="materials",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="learning_materials",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=LearningMaterialType.choices)
    file = models.FileField(
        upload_to="learning/materials/",
        storage=material_storage,
        blank=True,
    )
    external_url = models.URLField(blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=255, blank=True)
    size = models.PositiveBigIntegerField(blank=True, null=True)
    extension = models.CharField(max_length=20, blank=True)
    download_allowed = models.BooleanField(default=True)
    video_status = models.CharField(
        max_length=20,
        choices=VideoProcessingStatus.choices,
        blank=True,
    )
    duration_seconds = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        ordering = ("lesson", "id")
        indexes = [
            models.Index(
                fields=("course", "type"),
                name="learn_material_course_type",
            ),
        ]
        verbose_name = "Learning material"
        verbose_name_plural = "Learning materials"

    def clean(self):
        super().clean()
        if self.lesson_id and self.course_id:
            lesson_course_id = self.lesson.topic.module.course_id
            if lesson_course_id != self.course_id:
                raise ValidationError(
                    {"course": "Material course must match the lesson course."}
                )

    def __str__(self):
        return f"{self.course.code} / {self.lesson.title} / {self.title}"
