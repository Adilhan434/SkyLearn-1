import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("courses", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CourseTeachingAssignment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("teacher", "Teacher"),
                            ("teaching_assistant", "Teaching assistant"),
                        ],
                        max_length=30,
                    ),
                ),
                ("is_primary", models.BooleanField(default=False)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="teaching_assignments",
                        to="courses.course",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(app_label)s_%(class)s_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(app_label)s_%(class)s_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="course_teaching_assignments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Course teaching assignment",
                "verbose_name_plural": "Course teaching assignments",
                "ordering": ("course", "role", "user"),
                "indexes": [
                    models.Index(
                        fields=["course", "role"],
                        name="course_assign_course_role_idx",
                    ),
                    models.Index(
                        fields=["user", "role"],
                        name="course_assign_user_role_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("course", "user"),
                        name="course_unique_teaching_user",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(
                            ("is_primary", True),
                            ("role", "teacher"),
                        ),
                        fields=("course",),
                        name="course_unique_primary_teacher",
                    ),
                    models.CheckConstraint(
                        check=models.Q(
                            ("role", "teacher"),
                            ("is_primary", False),
                            _connector="OR",
                        ),
                        name="course_primary_teacher_only",
                    ),
                ],
            },
        ),
    ]
