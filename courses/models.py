from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from audit.models import AuditModel
from organization.models import Department, Faculty, Program, Semester


class CourseStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    UNDER_REVIEW = "under_review", "Under review"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class CourseLanguage(models.TextChoices):
    ENGLISH = "en", "English"
    KYRGYZ = "ky", "Kyrgyz"
    RUSSIAN = "ru", "Russian"


class Course(AuditModel):
    """Release 1 course metadata, independent from the legacy core course."""

    title = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    language = models.CharField(
        max_length=10,
        choices=CourseLanguage.choices,
        default=CourseLanguage.ENGLISH,
    )
    credits = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(60)]
    )
    semester = models.ForeignKey(
        Semester,
        on_delete=models.PROTECT,
        related_name="courses",
    )
    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.PROTECT,
        related_name="courses",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="courses",
    )
    program = models.ForeignKey(
        Program,
        on_delete=models.PROTECT,
        related_name="courses",
    )
    status = models.CharField(
        max_length=20,
        choices=CourseStatus.choices,
        default=CourseStatus.DRAFT,
        db_index=True,
    )
    start_date = models.DateField()
    end_date = models.DateField()
    cover = models.ImageField(upload_to="courses/covers/", blank=True)
    syllabus = models.FileField(upload_to="courses/syllabi/", blank=True)

    class Meta:
        ordering = ("code",)
        indexes = [
            models.Index(fields=("semester", "status"), name="course_sem_status_idx"),
            models.Index(fields=("faculty", "status"), name="course_fac_status_idx"),
        ]
        verbose_name = "Course"
        verbose_name_plural = "Courses"

    def clean(self):
        super().clean()
        errors = {}
        if self.end_date < self.start_date:
            errors["end_date"] = "End date must be on or after start date."
        if self.department_id and self.department.faculty_id != self.faculty_id:
            errors["department"] = "Department must belong to the selected faculty."
        if self.program_id and self.program.department_id != self.department_id:
            errors["program"] = "Program must belong to the selected department."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, allow_archived_update=False, **kwargs):
        if self.pk and not allow_archived_update:
            previous_status = (
                type(self).objects.filter(pk=self.pk)
                .values_list("status", flat=True)
                .first()
            )
            if previous_status == CourseStatus.ARCHIVED:
                raise ValidationError(
                    "Archived courses require an explicit archived update."
                )
        return super().save(*args, **kwargs)

    def archive(self):
        self.status = CourseStatus.ARCHIVED
        self.save(update_fields=("status", "updated_at"))

    def __str__(self):
        return f"{self.code} - {self.title}"

    # Teacher and Course Assistant assignments intentionally remain outside
    # this foundation model. They can be added later as explicit through
    # models without changing the course metadata contract.
