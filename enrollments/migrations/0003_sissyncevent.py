from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("enrollments", "0002_enrollment_unique_student_course"),
    ]

    operations = [
        migrations.CreateModel(
            name="SISSyncEvent",
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
                ("external_event_id", models.CharField(max_length=255, unique=True)),
                ("student_external_id", models.CharField(max_length=30)),
                ("course_code", models.CharField(max_length=50)),
                (
                    "action",
                    models.CharField(
                        choices=[("enroll", "Enroll"), ("withdraw", "Withdraw")],
                        max_length=20,
                    ),
                ),
                (
                    "result",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("created", "Created"),
                            ("reactivated", "Reactivated"),
                            ("withdrawn", "Withdrawn"),
                            ("unchanged", "Unchanged"),
                        ],
                        max_length=20,
                    ),
                ),
                ("processed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sis_sync_events_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "enrollment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sis_sync_events",
                        to="enrollments.enrollment",
                    ),
                ),
            ],
            options={
                "verbose_name": "SIS sync event",
                "verbose_name_plural": "SIS sync events",
                "ordering": ("-processed_at", "-id"),
            },
        ),
    ]
