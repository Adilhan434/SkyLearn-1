from django.db import models
from django.urls import reverse
from django.contrib.auth.models import AbstractUser
from config import settings
from django.utils.translation import gettext_lazy as _



FATHER = _("Father")
MOTHER = _("Mother")

RELATION_SHIP = (
    (FATHER, _("Father")),
    (MOTHER, _("Mother")),
)

GENDERS = ((_("M"), _("Male")), (_("F"), _("Female")))


class RoleCode(models.TextChoices):
    STUDENT = "student", _("Student")
    TEACHER = "teacher", _("Teacher")
    TEACHING_ASSISTANT = "teaching_assistant", _("Teaching Assistant")
    CONTENT_MANAGER = "content_manager", _("Content Manager")
    LMS_ADMIN = "lms_admin", _("LMS Admin")
    SUPER_ADMIN = "super_admin", _("Super Admin")


class LMSPermissionCode(models.TextChoices):
    COURSES_VIEW = "courses.view", _("View courses")
    COURSES_CREATE = "courses.create", _("Create courses")
    COURSES_EDIT = "courses.edit", _("Edit courses")
    COURSES_DELETE = "courses.delete", _("Delete courses")
    COURSES_SUBMIT_REVIEW = "courses.submit_review", _("Submit courses for review")
    COURSES_REVIEW = "courses.review", _("Review courses")
    COURSES_PUBLISH = "courses.publish", _("Publish courses")
    COURSES_ARCHIVE = "courses.archive", _("Archive courses")
    COURSES_COPY = "courses.copy", _("Copy courses")
    COURSE_STRUCTURE_VIEW = "course_structure.view", _("View course structure")
    COURSE_STRUCTURE_MANAGE = "course_structure.manage", _("Manage course structure")
    MATERIALS_VIEW = "materials.view", _("View learning materials")
    MATERIALS_UPLOAD = "materials.upload", _("Upload learning materials")
    MATERIALS_EDIT = "materials.edit", _("Edit learning materials")
    MATERIALS_DELETE = "materials.delete", _("Delete learning materials")
    ENROLLMENTS_VIEW = "enrollments.view", _("View enrollments")
    ENROLLMENTS_MANAGE = "enrollments.manage", _("Manage enrollments")
    CALENDAR_VIEW = "calendar.view", _("View calendar")
    CALENDAR_MANAGE = "calendar.manage", _("Manage calendar")


class LMSPermission(models.Model):
    code = models.CharField(
        max_length=100,
        choices=LMSPermissionCode.choices,
        unique=True,
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ("code",)
        verbose_name = "LMS permission"
        verbose_name_plural = "LMS permissions"

    def __str__(self):
        return self.code


class Role(models.Model):
    code = models.CharField(max_length=50, choices=RoleCode.choices, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(
        LMSPermission,
        through="RolePermission",
        related_name="roles",
        blank=True,
    )

    class Meta:
        ordering = ("code",)
        verbose_name = "Role"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.code


class User(AbstractUser):
    is_student = models.BooleanField(default=False)
    is_lecturer = models.BooleanField(default=False)
    is_parent = models.BooleanField(default=False)
    is_dep_head = models.BooleanField(default=False)
    is_accountant = models.BooleanField(default=False)
    gender = models.CharField(max_length=1, choices=GENDERS, blank=True, null=True)
    phone = models.CharField(max_length=60, blank=True, null=True)
    address = models.CharField(max_length=60, blank=True, null=True)
    picture = models.ImageField(
        upload_to="profile_pictures/%y/%m/%d/", default="default.png", null=True
    )
    email = models.EmailField(blank=True, null=True)
    first_name = models.CharField(max_length=120, blank=True, null=True)
    last_name = models.CharField(max_length=120, blank=True, null=True)
    roles = models.ManyToManyField(
        Role,
        through="UserRole",
        related_name="users",
        blank=True,
    )


    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"


    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_lms_permissions(self):
        if self.is_superuser:
            return set(LMSPermission.objects.values_list("code", flat=True))
        return set(
            LMSPermission.objects.filter(roles__users=self)
            .values_list("code", flat=True)
            .distinct()
        )

    def has_lms_permission(self, permission_code):
        if self.is_superuser:
            return True
        return LMSPermission.objects.filter(
            code=permission_code,
            roles__users=self,
        ).exists()


class UserRole(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="user_roles",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="user_roles",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("role__code",)
        constraints = [
            models.UniqueConstraint(
                fields=("user", "role"),
                name="unique_user_role",
            )
        ]
        verbose_name = "User role"
        verbose_name_plural = "User roles"

    def __str__(self):
        return f"{self.user} — {self.role.code}"


class RolePermission(models.Model):
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )
    permission = models.ForeignKey(
        LMSPermission,
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("role__code", "permission__code")
        constraints = [
            models.UniqueConstraint(
                fields=("role", "permission"),
                name="unique_role_lms_permission",
            )
        ]
        verbose_name = "Role permission"
        verbose_name_plural = "Role permissions"

    def __str__(self):
        return f"{self.role.code} - {self.permission.code}"


class Lecturer(models.Model):
    lecturer = models.OneToOneField(User, on_delete=models.CASCADE, related_name='lecturer_profile')
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='created_lecturers',
        limit_choices_to={'is_superuser': True},
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = "Lecturer"
        verbose_name_plural = "Lecturers"

    def __str__(self):
        return self.lecturer.get_full_name()
    
    def get_full_name(self):
        """Return the full name of the lecturer"""
        return self.lecturer.get_full_name()


class Group(models.Model):
    name = models.CharField(max_length=100)
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='created_groups',
        limit_choices_to={'is_superuser': True},
        null=True,
        blank=True
    )
    program = models.ForeignKey(
        'core.Program', on_delete=models.CASCADE, related_name='groups')

    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse("group_detail", kwargs={"pk": self.pk})
    
    def get_students(self):
        return self.students.all() 
    


class Student(models.Model):
    student = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    id_number = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
    )
    group = models.ForeignKey(
        Group, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='students'  # Добавляем related_name для удобства
    )
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='created_students',
        limit_choices_to={'is_superuser': True},
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = "Student"
        verbose_name_plural = "Students"

    def __str__(self):
        return self.student.get_full_name()
    
    def get_full_name(self):
        """Return the full name of the student"""
        return self.student.get_full_name()

class Parent(models.Model):
    """
    Connect student with their parent, parents can
    only view their connected students information
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parent_profile')
    student = models.ForeignKey(Student, null=True, on_delete=models.SET_NULL, related_name='parent_profiles')
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=60, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    # What is the relationship between the student and
    # the parent (i.e. father, mother, brother, sister)
    relation_ship = models.TextField(choices=RELATION_SHIP, blank=True)
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='created_parents',
        limit_choices_to={'is_superuser': True},
        null=True,
        blank=True
    )

    class Meta:
        ordering = ("-user__date_joined",)

    def __str__(self):
        return self.user.username


