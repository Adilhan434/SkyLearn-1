from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.db.models import ForeignKey
from django.test import TestCase

from audit.models import AuditModel
from organization.models import Faculty


class AuditModelTests(TestCase):
    def test_audit_model_is_abstract(self):
        self.assertTrue(AuditModel._meta.abstract)

    def test_release1_model_inherits_all_audit_fields(self):
        field_names = {field.name for field in Faculty._meta.get_fields()}
        self.assertTrue(
            {"created_at", "updated_at", "created_by", "updated_by"}.issubset(
                field_names
            )
        )
        self.assertIsInstance(Faculty._meta.get_field("created_by"), ForeignKey)
        self.assertIsInstance(Faculty._meta.get_field("updated_by"), ForeignKey)

    def test_audit_users_are_optional_and_timestamps_are_automatic(self):
        faculty = Faculty.objects.create(name="Engineering", code="ENG")

        self.assertIsNone(faculty.created_by)
        self.assertIsNone(faculty.updated_by)
        self.assertIsNotNone(faculty.created_at)
        self.assertIsNotNone(faculty.updated_at)

    def test_deleting_user_preserves_domain_record(self):
        user = get_user_model().objects.create_user(
            username="audit-user",
            password="test-password",
        )
        faculty = Faculty.objects.create(
            name="Engineering",
            code="ENG",
            created_by=user,
            updated_by=user,
        )

        user.delete()
        faculty.refresh_from_db()

        self.assertIsNone(faculty.created_by)
        self.assertIsNone(faculty.updated_by)

    def test_admin_mixin_populates_audit_users(self):
        creator = get_user_model().objects.create_superuser(
            username="audit-admin",
            email="audit-admin@example.invalid",
            password="test-password",
        )
        request = RequestFactory().post("/admin/organization/faculty/add/")
        request.user = creator
        faculty = Faculty(name="Engineering", code="ENG")

        admin.site._registry[Faculty].save_model(
            request,
            faculty,
            form=None,
            change=False,
        )

        self.assertEqual(faculty.created_by, creator)
        self.assertEqual(faculty.updated_by, creator)
