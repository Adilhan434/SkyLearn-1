from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("courses", "0003_course_code_case_insensitive"),
    ]

    operations = [
        migrations.AlterField(
            model_name="course",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("under_review", "Under review"),
                    ("needs_revision", "Needs revision"),
                    ("published", "Published"),
                    ("archived", "Archived"),
                ],
                db_index=True,
                default="draft",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="course",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="course",
            name="published_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="courses_published",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="course",
            name="review_comment",
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name="CourseStatusHistory",
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
                    "action",
                    models.CharField(
                        choices=[
                            ("submit_review", "Submit for review"),
                            ("return_revision", "Return for revision"),
                            ("publish", "Publish"),
                            ("archive", "Archive"),
                            ("restore", "Restore"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "from_status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("under_review", "Under review"),
                            ("needs_revision", "Needs revision"),
                            ("published", "Published"),
                            ("archived", "Archived"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "to_status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("under_review", "Under review"),
                            ("needs_revision", "Needs revision"),
                            ("published", "Published"),
                            ("archived", "Archived"),
                        ],
                        max_length=20,
                    ),
                ),
                ("comment", models.TextField(blank=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_history",
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
            ],
            options={
                "verbose_name": "Course status history",
                "verbose_name_plural": "Course status history",
                "ordering": ("-created_at", "-id"),
            },
        ),
        migrations.AddIndex(
            model_name="coursestatushistory",
            index=models.Index(
                fields=["course", "created_at"],
                name="course_history_course_time_idx",
            ),
        ),
    ]
