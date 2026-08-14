from datetime import date

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from courses.admin import CourseAdmin
from courses.models import (
    Course,
    CourseLanguage,
    CourseStatus,
)
from organization.models import DegreeLevel, Department, Faculty, Program, Semester


class CourseModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="course-creator",
            password="test-password",
        )
        self.faculty = Faculty.objects.create(name="Engineering", code="ENG")
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
        self.semester = Semester.objects.create(
            name="Fall 2026",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )

    def make_course(self, **overrides):
        values = {
            "title": "Introduction to Programming",
            "code": "CS101",
            "description": "Programming foundations",
            "language": CourseLanguage.ENGLISH,
            "credits": 5,
            "semester": self.semester,
            "faculty": self.faculty,
            "department": self.department,
            "program": self.program,
            "status": CourseStatus.DRAFT,
            "start_date": date(2026, 9, 1),
            "end_date": date(2026, 12, 20),
            "created_by": self.user,
            "updated_by": self.user,
        }
        values.update(overrides)
        return Course.objects.create(**values)

    def test_course_creation_and_string_representation(self):
        course = self.make_course()

        self.assertEqual(str(course), "CS101 - Introduction to Programming")
        self.assertEqual(course.status, CourseStatus.DRAFT)
        self.assertEqual(course.created_by, self.user)
        self.assertIsNotNone(course.created_at)
        self.assertIsNotNone(course.updated_at)

    def test_course_code_is_unique(self):
        self.make_course()
        with self.assertRaises(IntegrityError):
            self.make_course(title="Duplicate course", code="cs101")

    def test_course_code_is_trimmed_and_normalized(self):
        course = self.make_course(code="  cs-101  ")

        self.assertEqual(course.code, "CS-101")
        course.refresh_from_db()
        self.assertEqual(course.code, "CS-101")

    def test_course_dates_must_be_ordered(self):
        course = Course(
            title="Invalid dates",
            code="BAD-DATES",
            credits=3,
            semester=self.semester,
            faculty=self.faculty,
            department=self.department,
            program=self.program,
            start_date=date(2026, 12, 1),
            end_date=date(2026, 9, 1),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "End date must be on or after start date.",
        ):
            course.full_clean()

    def test_organization_relationships_must_be_consistent(self):
        other_faculty = Faculty.objects.create(name="Business", code="BUS")
        course = self.make_course(faculty=other_faculty)

        with self.assertRaisesMessage(
            ValidationError,
            "Department must belong to the selected faculty.",
        ):
            course.full_clean()

    def test_archived_course_rejects_regular_updates(self):
        course = self.make_course(status=CourseStatus.ARCHIVED)
        course.title = "Unexpected change"

        with self.assertRaisesMessage(
            ValidationError,
            "Archived courses require an explicit archived update.",
        ):
            course.save()

        course.refresh_from_db()
        self.assertEqual(course.title, "Introduction to Programming")

    def test_archived_course_can_be_updated_explicitly(self):
        course = self.make_course(status=CourseStatus.ARCHIVED)
        course.title = "Approved correction"
        course.save(allow_archived_update=True, update_fields=("title",))

        course.refresh_from_db()
        self.assertEqual(course.title, "Approved correction")

    def test_course_can_be_archived_through_explicit_method(self):
        course = self.make_course(status=CourseStatus.PUBLISHED)
        course.archive()

        course.refresh_from_db()
        self.assertEqual(course.status, CourseStatus.ARCHIVED)

    def test_course_is_registered_in_admin(self):
        self.assertIsInstance(admin.site._registry[Course], CourseAdmin)

    def test_course_domain_contains_teaching_assignment(self):
        app_models = {model.__name__ for model in Course._meta.app_config.get_models()}
        self.assertEqual(
            app_models,
            {"Course", "CourseTeachingAssignment", "CourseStatusHistory"},
        )
