from importlib import import_module

from django.apps import apps
from django.contrib import admin
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import Role, RoleCode, User, UserRole


class RoleModelTests(TestCase):
    def test_release1_roles_are_created_by_migration(self):
        self.assertSetEqual(
            set(Role.objects.values_list("code", flat=True)),
            set(RoleCode.values),
        )

    def test_user_can_have_multiple_roles(self):
        user = User.objects.create_user(username="multi-role-user")
        student = Role.objects.get(code=RoleCode.STUDENT)
        content_manager = Role.objects.get(code=RoleCode.CONTENT_MANAGER)

        user.roles.add(student, content_manager)

        self.assertSetEqual(
            set(user.roles.values_list("code", flat=True)),
            {RoleCode.STUDENT, RoleCode.CONTENT_MANAGER},
        )

    def test_same_role_cannot_be_assigned_twice(self):
        user = User.objects.create_user(username="student-user")
        student = Role.objects.get(code=RoleCode.STUDENT)
        UserRole.objects.create(user=user, role=student)

        with self.assertRaises(IntegrityError), transaction.atomic():
            UserRole.objects.create(user=user, role=student)

    def test_legacy_role_flags_remain_available(self):
        user = User.objects.create_user(username="legacy-student")
        User.objects.filter(pk=user.pk).update(is_student=True)
        user.refresh_from_db()

        self.assertTrue(user.is_student)
        self.assertTrue(hasattr(user, "is_lecturer"))

    def test_data_migration_maps_supported_legacy_flags(self):
        user = User.objects.create_user(username="legacy-multi-role")
        User.objects.filter(pk=user.pk).update(
            is_student=True,
            is_lecturer=True,
            is_superuser=True,
        )
        migration = import_module(
            "accounts.migrations.0008_seed_release1_roles"
        )

        migration.seed_roles_and_migrate_legacy_flags(apps, None)

        self.assertSetEqual(
            set(user.roles.values_list("code", flat=True)),
            {
                RoleCode.STUDENT,
                RoleCode.TEACHER,
                RoleCode.SUPER_ADMIN,
            },
        )

    def test_role_models_are_registered_in_admin(self):
        self.assertTrue(admin.site.is_registered(Role))
        self.assertTrue(admin.site.is_registered(UserRole))


class LegacyRoleSynchronizationTests(TestCase):
    def test_enabling_legacy_flag_assigns_role(self):
        user = User.objects.create_user(username="legacy-teacher")

        user.is_lecturer = True
        user.save(update_fields=["is_lecturer"])

        self.assertTrue(user.roles.filter(code=RoleCode.TEACHER).exists())

    def test_disabling_legacy_flag_removes_role(self):
        user = User.objects.create_user(username="former-student")
        user.is_student = True
        user.save(update_fields=["is_student"])

        user.is_student = False
        user.save(update_fields=["is_student"])

        self.assertFalse(user.roles.filter(code=RoleCode.STUDENT).exists())

    def test_assigning_role_updates_legacy_flag(self):
        user = User.objects.create_user(username="new-student")
        student_role = Role.objects.get(code=RoleCode.STUDENT)

        user.roles.add(student_role)
        user.refresh_from_db()

        self.assertTrue(user.is_student)

    def test_removing_role_updates_legacy_flag(self):
        user = User.objects.create_user(username="former-teacher")
        teacher_role = Role.objects.get(code=RoleCode.TEACHER)
        user.roles.add(teacher_role)

        user.roles.remove(teacher_role)
        user.refresh_from_db()

        self.assertFalse(user.is_lecturer)

    def test_direct_user_role_changes_superuser_flag(self):
        user = User.objects.create_user(username="temporary-super-admin")
        super_admin = Role.objects.get(code=RoleCode.SUPER_ADMIN)

        assignment = UserRole.objects.create(user=user, role=super_admin)
        user.refresh_from_db()
        self.assertTrue(user.is_superuser)

        assignment.delete()
        user.refresh_from_db()
        self.assertFalse(user.is_superuser)

    def test_unmapped_role_does_not_change_legacy_flags(self):
        user = User.objects.create_user(username="content-manager")
        content_manager = Role.objects.get(code=RoleCode.CONTENT_MANAGER)

        user.roles.add(content_manager)
        user.refresh_from_db()

        self.assertFalse(user.is_student)
        self.assertFalse(user.is_lecturer)
        self.assertFalse(user.is_superuser)
