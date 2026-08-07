from datetime import date

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from organization.models import (
    DegreeLevel,
    Department,
    Faculty,
    Group,
    Program,
    Semester,
)


class OrganizationModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="organization-admin",
            password="test-password",
        )
        self.faculty = Faculty.objects.create(
            name="Faculty of Engineering",
            code="ENG",
            created_by=self.user,
            updated_by=self.user,
        )
        self.department = Department.objects.create(
            faculty=self.faculty,
            name="Computer Science",
            code="CS",
        )
        self.program = Program.objects.create(
            department=self.department,
            name="Software Engineering",
            code="SE",
            degree_level=DegreeLevel.BACHELOR,
        )

    def test_faculty_has_audit_fields_and_string_representation(self):
        self.assertEqual(str(self.faculty), "ENG - Faculty of Engineering")
        self.assertIsNotNone(self.faculty.created_at)
        self.assertIsNotNone(self.faculty.updated_at)
        self.assertEqual(self.faculty.created_by, self.user)

    def test_faculty_code_is_unique(self):
        with self.assertRaises(IntegrityError):
            Faculty.objects.create(name="Other", code="ENG")

    def test_department_code_is_unique_within_faculty(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Department.objects.create(
                faculty=self.faculty,
                name="Duplicate CS",
                code="CS",
            )

        other_faculty = Faculty.objects.create(name="Science", code="SCI")
        duplicate_code = Department.objects.create(
            faculty=other_faculty,
            name="Computer Science",
            code="CS",
        )
        self.assertEqual(duplicate_code.code, "CS")

    def test_program_code_is_unique_within_department(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Program.objects.create(
                department=self.department,
                name="Duplicate",
                code="SE",
                degree_level=DegreeLevel.MASTER,
            )

    def test_group_is_unique_for_program_name_and_admission_year(self):
        Group.objects.create(
            program=self.program,
            name="SE-26",
            admission_year=2026,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Group.objects.create(
                program=self.program,
                name="SE-26",
                admission_year=2026,
            )

    def test_semester_rejects_end_date_before_start_date(self):
        semester = Semester(
            name="Fall 2026",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 8, 31),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "End date must be on or after start date.",
        ):
            semester.full_clean()

    def test_code_fields_are_indexed(self):
        self.assertTrue(Faculty._meta.get_field("code").unique)
        self.assertTrue(Department._meta.get_field("code").db_index)
        self.assertTrue(Program._meta.get_field("code").db_index)

    def test_all_organization_models_are_registered_in_admin(self):
        for model in (Faculty, Department, Program, Group, Semester):
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)
