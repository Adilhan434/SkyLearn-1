from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("courses", "0005_coursetemplate"),
    ]

    operations = [
        migrations.CreateModel(
            name="CourseHistoryEvent",
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
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("course_created", "Course created"),
                            ("course_updated", "Course updated"),
                            ("module_created", "Module created"),
                            ("module_updated", "Module updated"),
                            ("module_deleted", "Module deleted"),
                            ("topic_created", "Topic created"),
                            ("topic_updated", "Topic updated"),
                            ("topic_deleted", "Topic deleted"),
                            ("lesson_created", "Lesson created"),
                            ("lesson_updated", "Lesson updated"),
                            ("lesson_deleted", "Lesson deleted"),
                            ("material_uploaded", "Material uploaded"),
                            ("material_deleted", "Material deleted"),
                            ("submitted_for_review", "Submitted for review"),
                            ("returned_for_revision", "Returned for revision"),
                            ("published", "Published"),
                            ("archived", "Archived"),
                            ("restored", "Restored"),
                            ("copied", "Copied"),
                        ],
                        max_length=40,
                    ),
                ),
                (
                    "object_type",
                    models.CharField(
                        choices=[
                            ("course", "Course"),
                            ("module", "Module"),
                            ("topic", "Topic"),
                            ("lesson", "Lesson"),
                            ("material", "Material"),
                        ],
                        max_length=20,
                    ),
                ),
                ("object_id", models.PositiveBigIntegerField()),
                ("object_title", models.CharField(max_length=255)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="course_history_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="history_events",
                        to="courses.course",
                    ),
                ),
            ],
            options={
                "verbose_name": "Course history event",
                "verbose_name_plural": "Course history events",
                "ordering": ("-created_at", "-id"),
                "indexes": [
                    models.Index(
                        fields=["course", "created_at"],
                        name="audit_history_course_time_idx",
                    )
                ],
            },
        ),
    ]
