from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from accounts.models import RoleCode
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


class CourseTeachingRole(models.TextChoices):
    TEACHER = "teacher", "Teacher"
    TEACHING_ASSISTANT = "teaching_assistant", "Teaching assistant"


class CourseTeachingAssignment(AuditModel):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="teaching_assignments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_teaching_assignments",
    )
    role = models.CharField(
        max_length=30,
        choices=CourseTeachingRole.choices,
    )
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ("course", "role", "user")
        indexes = [
            models.Index(
                fields=("course", "role"),
                name="course_assign_course_role_idx",
            ),
            models.Index(
                fields=("user", "role"),
                name="course_assign_user_role_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("course", "user"),
                name="course_unique_teaching_user",
            ),
            models.UniqueConstraint(
                fields=("course",),
                condition=Q(
                    role=CourseTeachingRole.TEACHER,
                    is_primary=True,
                ),
                name="course_unique_primary_teacher",
            ),
            models.CheckConstraint(
                check=Q(role=CourseTeachingRole.TEACHER)
                | Q(is_primary=False),
                name="course_primary_teacher_only",
            ),
        ]
        verbose_name = "Course teaching assignment"
        verbose_name_plural = "Course teaching assignments"

    def clean(self):
        super().clean()
        errors = {}
        if self.user_id:
            if not self.user.is_active:
                errors["user"] = "Only an active user can be assigned."
            expected_role = (
                RoleCode.TEACHER
                if self.role == CourseTeachingRole.TEACHER
                else RoleCode.TEACHING_ASSISTANT
            )
            if not self.user.roles.filter(code=expected_role).exists():
                errors["user"] = (
                    f"User must have the {expected_role} role."
                )
        if self.is_primary and self.role != CourseTeachingRole.TEACHER:
            errors["is_primary"] = (
                "Only a teacher assignment can be primary."
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.course.code} - {self.user} ({self.role})"
