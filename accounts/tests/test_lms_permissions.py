from types import SimpleNamespace

from django.contrib import admin
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.api.v1.permissions import HasLMSPermission
from accounts.models import (
    LMSPermission,
    LMSPermissionCode,
    Role,
    RoleCode,
    RolePermission,
    User,
)
from accounts.permission_defaults import RELEASE1_ROLE_PERMISSIONS


class LMSPermissionModelTests(TestCase):
    def test_data_migration_creates_complete_permission_catalog(self):
        self.assertSetEqual(
            set(LMSPermission.objects.values_list("code", flat=True)),
            set(LMSPermissionCode.values),
        )

    def test_roles_receive_expected_default_permissions(self):
        all_codes = set(LMSPermissionCode.values)
        for role_code, expected in RELEASE1_ROLE_PERMISSIONS.items():
            role = Role.objects.get(code=role_code)
            expected_codes = all_codes if expected == "*" else expected
            self.assertSetEqual(
                set(role.permissions.values_list("code", flat=True)),
                set(expected_codes),
                msg=f"Unexpected permissions for {role_code}",
            )

    def test_same_permission_cannot_be_assigned_to_role_twice(self):
        role = Role.objects.get(code=RoleCode.STUDENT)
        permission = LMSPermission.objects.get(
            code=LMSPermissionCode.COURSES_VIEW
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            RolePermission.objects.create(role=role, permission=permission)

    def test_user_permissions_are_union_of_all_roles(self):
        user = User.objects.create_user(username="multi-permission-user")
        user.roles.add(
            Role.objects.get(code=RoleCode.STUDENT),
            Role.objects.get(code=RoleCode.TEACHER),
        )

        expected = set(RELEASE1_ROLE_PERMISSIONS[RoleCode.STUDENT]) | set(
            RELEASE1_ROLE_PERMISSIONS[RoleCode.TEACHER]
        )
        self.assertSetEqual(user.get_lms_permissions(), expected)

    def test_has_lms_permission_uses_stable_code(self):
        user = User.objects.create_user(username="permission-check-user")
        user.roles.add(Role.objects.get(code=RoleCode.TEACHER))

        self.assertTrue(
            user.has_lms_permission(LMSPermissionCode.COURSES_EDIT)
        )
        self.assertFalse(
            user.has_lms_permission(LMSPermissionCode.COURSES_PUBLISH)
        )

    def test_permission_models_are_registered_in_admin(self):
        self.assertTrue(admin.site.is_registered(LMSPermission))
        self.assertTrue(admin.site.is_registered(RolePermission))


class HasLMSPermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teacher-permission")
        self.user.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.permission = HasLMSPermission()

    def test_allows_user_with_required_permission(self):
        request = SimpleNamespace(user=self.user)
        view = SimpleNamespace(
            required_lms_permission=LMSPermissionCode.COURSES_EDIT
        )

        self.assertTrue(self.permission.has_permission(request, view))

    def test_denies_user_without_required_permission(self):
        request = SimpleNamespace(user=self.user)
        view = SimpleNamespace(
            required_lms_permission=LMSPermissionCode.COURSES_PUBLISH
        )

        self.assertFalse(self.permission.has_permission(request, view))

    def test_denies_anonymous_user(self):
        request = SimpleNamespace(user=AnonymousUser())
        view = SimpleNamespace(
            required_lms_permission=LMSPermissionCode.COURSES_VIEW
        )

        self.assertFalse(self.permission.has_permission(request, view))

    def test_requires_permission_declaration_on_view(self):
        request = SimpleNamespace(user=self.user)

        with self.assertRaisesMessage(RuntimeError, "required_lms_permission"):
            self.permission.has_permission(request, SimpleNamespace())
