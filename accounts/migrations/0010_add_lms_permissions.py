from django.db import migrations, models
import django.db.models.deletion


PERMISSIONS = {
    "courses.view": "View courses",
    "courses.create": "Create courses",
    "courses.edit": "Edit courses",
    "courses.delete": "Delete courses",
    "courses.submit_review": "Submit courses for review",
    "courses.review": "Review courses",
    "courses.publish": "Publish courses",
    "courses.archive": "Archive courses",
    "courses.copy": "Copy courses",
    "course_structure.view": "View course structure",
    "course_structure.manage": "Manage course structure",
    "materials.view": "View learning materials",
    "materials.upload": "Upload learning materials",
    "materials.edit": "Edit learning materials",
    "materials.delete": "Delete learning materials",
    "enrollments.view": "View enrollments",
    "enrollments.manage": "Manage enrollments",
    "calendar.view": "View calendar",
    "calendar.manage": "Manage calendar",
}

ROLE_PERMISSIONS = {
    "student": {
        "courses.view",
        "course_structure.view",
        "materials.view",
        "calendar.view",
    },
    "teacher": {
        "courses.view", "courses.create", "courses.edit",
        "courses.submit_review", "course_structure.view",
        "course_structure.manage", "materials.view", "materials.upload",
        "materials.edit", "materials.delete", "enrollments.view",
        "calendar.view", "calendar.manage",
    },
    "teaching_assistant": {
        "courses.view", "course_structure.view", "course_structure.manage",
        "materials.view", "materials.upload", "materials.edit",
        "enrollments.view", "calendar.view",
    },
    "content_manager": {
        "courses.view", "courses.create", "courses.edit", "courses.delete",
        "courses.submit_review", "courses.review", "courses.publish",
        "courses.copy", "course_structure.view", "course_structure.manage",
        "materials.view", "materials.upload", "materials.edit",
        "materials.delete", "calendar.view", "calendar.manage",
    },
    "lms_admin": set(PERMISSIONS),
    "super_admin": set(PERMISSIONS),
}


def seed_lms_permissions(apps, schema_editor):
    LMSPermission = apps.get_model("accounts", "LMSPermission")
    Role = apps.get_model("accounts", "Role")
    RolePermission = apps.get_model("accounts", "RolePermission")

    permissions = {}
    for code, name in PERMISSIONS.items():
        permission, _ = LMSPermission.objects.update_or_create(
            code=code,
            defaults={"name": name},
        )
        permissions[code] = permission

    assignments = []
    for role in Role.objects.filter(code__in=ROLE_PERMISSIONS):
        for code in ROLE_PERMISSIONS[role.code]:
            assignments.append(
                RolePermission(role=role, permission=permissions[code])
            )
    RolePermission.objects.bulk_create(assignments, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0009_add_student_id_number")]

    operations = [
        migrations.CreateModel(
            name="LMSPermission",
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
                    "code",
                    models.CharField(
                        choices=[
                            ("courses.view", "View courses"),
                            ("courses.create", "Create courses"),
                            ("courses.edit", "Edit courses"),
                            ("courses.delete", "Delete courses"),
                            ("courses.submit_review", "Submit courses for review"),
                            ("courses.review", "Review courses"),
                            ("courses.publish", "Publish courses"),
                            ("courses.archive", "Archive courses"),
                            ("courses.copy", "Copy courses"),
                            ("course_structure.view", "View course structure"),
                            ("course_structure.manage", "Manage course structure"),
                            ("materials.view", "View learning materials"),
                            ("materials.upload", "Upload learning materials"),
                            ("materials.edit", "Edit learning materials"),
                            ("materials.delete", "Delete learning materials"),
                            ("enrollments.view", "View enrollments"),
                            ("enrollments.manage", "Manage enrollments"),
                            ("calendar.view", "View calendar"),
                            ("calendar.manage", "Manage calendar"),
                        ],
                        max_length=100,
                        unique=True,
                    ),
                ),
                ("name", models.CharField(max_length=150)),
                ("description", models.TextField(blank=True)),
            ],
            options={
                "verbose_name": "LMS permission",
                "verbose_name_plural": "LMS permissions",
                "ordering": ("code",),
            },
        ),
        migrations.CreateModel(
            name="RolePermission",
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
                ("assigned_at", models.DateTimeField(auto_now_add=True)),
                (
                    "permission",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="role_permissions",
                        to="accounts.lmspermission",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="role_permissions",
                        to="accounts.role",
                    ),
                ),
            ],
            options={
                "verbose_name": "Role permission",
                "verbose_name_plural": "Role permissions",
                "ordering": ("role__code", "permission__code"),
            },
        ),
        migrations.AddField(
            model_name="role",
            name="permissions",
            field=models.ManyToManyField(
                blank=True,
                related_name="roles",
                through="accounts.RolePermission",
                to="accounts.lmspermission",
            ),
        ),
        migrations.AddConstraint(
            model_name="rolepermission",
            constraint=models.UniqueConstraint(
                fields=("role", "permission"),
                name="unique_role_lms_permission",
            ),
        ),
        migrations.RunPython(
            seed_lms_permissions,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
