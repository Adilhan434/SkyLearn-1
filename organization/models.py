from django.core.exceptions import ValidationError
from django.db import models

from audit.models import AuditModel


class Faculty(AuditModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        indexes = [models.Index(fields=("code",), name="org_faculty_code_idx")]
        verbose_name = "Faculty"
        verbose_name_plural = "Faculties"

    def __str__(self):
        return f"{self.code} - {self.name}"


class Department(AuditModel):
    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.PROTECT,
        related_name="departments",
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("faculty__name", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("faculty", "code"),
                name="org_unique_department_code_per_faculty",
            )
        ]
        verbose_name = "Department"
        verbose_name_plural = "Departments"

    def __str__(self):
        return f"{self.code} - {self.name}"


class DegreeLevel(models.TextChoices):
    ASSOCIATE = "associate", "Associate"
    BACHELOR = "bachelor", "Bachelor"
    MASTER = "master", "Master"
    DOCTORATE = "doctorate", "Doctorate"


class Program(AuditModel):
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="programs",
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, db_index=True)
    degree_level = models.CharField(
        max_length=20,
        choices=DegreeLevel.choices,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("department__name", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("department", "code"),
                name="org_unique_program_code_per_department",
            )
        ]
        verbose_name = "Program"
        verbose_name_plural = "Programs"

    def __str__(self):
        return f"{self.code} - {self.name}"


class Group(AuditModel):
    program = models.ForeignKey(
        Program,
        on_delete=models.PROTECT,
        related_name="groups",
    )
    name = models.CharField(max_length=100)
    admission_year = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-admission_year", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("program", "name", "admission_year"),
                name="org_unique_group_per_program_year",
            )
        ]
        verbose_name = "Group"
        verbose_name_plural = "Groups"

    def __str__(self):
        return f"{self.name} ({self.admission_year})"


class Semester(AuditModel):
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-start_date", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("name", "start_date", "end_date"),
                name="org_unique_semester_period",
            )
        ]
        verbose_name = "Semester"
        verbose_name_plural = "Semesters"

    def clean(self):
        super().clean()
        if self.end_date < self.start_date:
            raise ValidationError(
                {"end_date": "End date must be on or after start date."}
            )

    def __str__(self):
        return f"{self.name}: {self.start_date} - {self.end_date}"
