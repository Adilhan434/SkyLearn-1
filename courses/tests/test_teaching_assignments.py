from datetime import date

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import Role, RoleCode, User
from courses.admin import CourseTeachingAssignmentAdmin
from courses.models import (
    Course,
    CourseTeachingAssignment,
    CourseTeachingRole,
)
from organization.models import DegreeLevel, Department, Faculty, Program, Semester


class CourseTeachingAssignmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        faculty = Faculty.objects.create(name="Engineering", code="ENG-ASSIGN")
        department = Department.objects.create(
            faculty=faculty,
            name="Computer Science",
            code="CS-ASSIGN",
        )
        program = Program.objects.create(
            department=department,
            name="Software Engineering",
            code="SE-ASSIGN",
            degree_level=DegreeLevel.BACHELOR,
        )
        semester = Semester.objects.create(
            name="Fall Assignments 2026",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        cls.course = Course.objects.create(
            title="Assignment Course",
            code="ASSIGN-101",
            credits=5,
            semester=semester,
            faculty=faculty,
            department=department,
            program=program,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        cls.teacher_role = Role.objects.get(code=RoleCode.TEACHER)
        cls.assistant_role = Role.objects.get(
            code=RoleCode.TEACHING_ASSISTANT
        )

    def make_user(self, username, role, is_active=True):
        user = User.objects.create_user(
            username=username,
            is_active=is_active,
        )
        user.roles.add(role)
        return user

    def test_creates_primary_teacher_with_audit_fields(self):
        teacher = self.make_user("primary-teacher", self.teacher_role)

        assignment = CourseTeachingAssignment.objects.create(
            course=self.course,
            user=teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
            created_by=teacher,
            updated_by=teacher,
        )

        self.assertEqual(assignment.course, self.course)
        self.assertTrue(assignment.is_primary)
        self.assertIsNotNone(assignment.created_at)
        self.assertEqual(
            str(assignment),
            "ASSIGN-101 - primary-teacher (teacher)",
        )

    def test_allows_multiple_assistants(self):
        first = self.make_user("assistant-one", self.assistant_role)
        second = self.make_user("assistant-two", self.assistant_role)

        for assistant in (first, second):
            assignment = CourseTeachingAssignment(
                course=self.course,
                user=assistant,
                role=CourseTeachingRole.TEACHING_ASSISTANT,
            )
            assignment.full_clean()
            assignment.save()

        self.assertEqual(self.course.teaching_assignments.count(), 2)

    def test_rejects_inactive_teacher(self):
        teacher = self.make_user(
            "inactive-teacher",
            self.teacher_role,
            is_active=False,
        )
        assignment = CourseTeachingAssignment(
            course=self.course,
            user=teacher,
            role=CourseTeachingRole.TEACHER,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Only an active user can be assigned.",
        ):
            assignment.full_clean()

    def test_rejects_user_without_matching_role(self):
        student = self.make_user(
            "student-as-teacher",
            Role.objects.get(code=RoleCode.STUDENT),
        )
        assignment = CourseTeachingAssignment(
            course=self.course,
            user=student,
            role=CourseTeachingRole.TEACHER,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "User must have the teacher role.",
        ):
            assignment.full_clean()

    def test_assistant_cannot_be_primary(self):
        assistant = self.make_user("primary-assistant", self.assistant_role)
        assignment = CourseTeachingAssignment(
            course=self.course,
            user=assistant,
            role=CourseTeachingRole.TEACHING_ASSISTANT,
            is_primary=True,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Only a teacher assignment can be primary.",
        ):
            assignment.full_clean()

    def test_user_cannot_have_two_assignments_in_same_course(self):
        teacher = self.make_user("duplicate-teacher", self.teacher_role)
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=teacher,
            role=CourseTeachingRole.TEACHER,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            CourseTeachingAssignment.objects.create(
                course=self.course,
                user=teacher,
                role=CourseTeachingRole.TEACHING_ASSISTANT,
            )

    def test_course_cannot_have_two_primary_teachers(self):
        first = self.make_user("primary-one", self.teacher_role)
        second = self.make_user("primary-two", self.teacher_role)
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=first,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            CourseTeachingAssignment.objects.create(
                course=self.course,
                user=second,
                role=CourseTeachingRole.TEACHER,
                is_primary=True,
            )

    def test_model_is_registered_in_admin(self):
        self.assertIsInstance(
            admin.site._registry[CourseTeachingAssignment],
            CourseTeachingAssignmentAdmin,
        )
