from django.db import migrations


RELEASE1_ROLES = {
    "student": "Student",
    "teacher": "Teacher",
    "teaching_assistant": "Teaching Assistant",
    "content_manager": "Content Manager",
    "lms_admin": "LMS Admin",
    "super_admin": "Super Admin",
}


def seed_roles_and_migrate_legacy_flags(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    User = apps.get_model("accounts", "User")
    UserRole = apps.get_model("accounts", "UserRole")

    roles = {}
    for code, name in RELEASE1_ROLES.items():
        role, _ = Role.objects.update_or_create(
            code=code,
            defaults={"name": name},
        )
        roles[code] = role

    assignments = []
    for user in User.objects.all().iterator():
        if user.is_student:
            assignments.append(UserRole(user_id=user.pk, role=roles["student"]))
        if user.is_lecturer:
            assignments.append(UserRole(user_id=user.pk, role=roles["teacher"]))
        if user.is_superuser:
            assignments.append(
                UserRole(user_id=user.pk, role=roles["super_admin"])
            )

    UserRole.objects.bulk_create(assignments, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_add_role_models"),
    ]

    operations = [
        migrations.RunPython(
            seed_roles_and_migrate_legacy_flags,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
