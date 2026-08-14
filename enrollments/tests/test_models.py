from datetime import date

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import Role, RoleCode
from courses.models import Course
from enrollments.admin import EnrollmentAdmin
from enrollments.models import Enrollment, EnrollmentSource, EnrollmentStatus
from organization.models import DegreeLevel, Department, Faculty, Program, Semester


class EnrollmentModelTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.actor = user_model.objects.create_user(username="enrollment-admin")
        self.student = user_model.objects.create_user(username="student-2026")
        self.student.roles.add(Role.objects.get(code=RoleCode.STUDENT))
        faculty = Faculty.objects.create(name="Engineering", code="ENG")
        department = Department.objects.create(
            faculty=faculty,
            name="Computer Science",
            code="CS",
        )
        program = Program.objects.create(
            department=department,
            name="Software Engineering",
            code="SE",
            degree_level=DegreeLevel.BACHELOR,
        )
        semester = Semester.objects.create(
            name="Fall 2026",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        self.course = Course.objects.create(
            title="Introduction to Programming",
            code="CS101",
            credits=5,
            semester=semester,
            faculty=faculty,
            department=department,
            program=program,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
            created_by=self.actor,
            updated_by=self.actor,
        )

    def test_manual_active_enrollment_defaults_and_audit_fields(self):
        enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            created_by=self.actor,
            updated_by=self.actor,
        )

        self.assertEqual(enrollment.status, EnrollmentStatus.ACTIVE)
        self.assertEqual(enrollment.source, EnrollmentSource.MANUAL)
        self.assertEqual(enrollment.external_sis_id, "")
        self.assertIsNotNone(enrollment.enrolled_at)
        self.assertIsNotNone(enrollment.created_at)
        self.assertIsNotNone(enrollment.updated_at)
        self.assertEqual(enrollment.created_by, self.actor)
        self.assertEqual(enrollment.updated_by, self.actor)
        self.assertEqual(
            str(enrollment),
            "student-2026 / CS101 (active)",
        )

    def test_sis_enrollment_supports_lifecycle_status_and_external_id(self):
        enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            status=EnrollmentStatus.SUSPENDED,
            source=EnrollmentSource.SIS_SYNC,
            external_sis_id="sis-enrollment-42",
        )

        self.assertEqual(enrollment.status, EnrollmentStatus.SUSPENDED)
        self.assertEqual(enrollment.source, EnrollmentSource.SIS_SYNC)
        self.assertEqual(enrollment.external_sis_id, "sis-enrollment-42")

    def test_enrollment_is_registered_in_admin(self):
        self.assertIsInstance(
            admin.site._registry[Enrollment],
            EnrollmentAdmin,
        )

    def test_student_and_course_pair_is_unique(self):
        Enrollment.objects.create(
            student=self.student,
            course=self.course,
            status=EnrollmentStatus.WITHDRAWN,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Enrollment.objects.create(
                student=self.student,
                course=self.course,
                status=EnrollmentStatus.ACTIVE,
            )

        self.assertEqual(
            Enrollment.objects.filter(
                student=self.student,
                course=self.course,
            ).count(),
            1,
        )
