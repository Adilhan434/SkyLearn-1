from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Group, Student
from core.models import AcademicYear, Course, Program, Semester
from result.models import Grade_1st_module, Grade_2nd_module, Grade_semester


User = get_user_model()


class ResultViewsTests(APITestCase):
    def setUp(self):
        self.program = Program.objects.create(name="Computer Science")
        self.group = Group.objects.create(name="CS-1", program=self.program)
        self.academic_year = AcademicYear.objects.create(
            year=2026,
            program=self.program,
            is_current=True,
        )
        self.semester = Semester.objects.create(
            name="First",
            academic_year=self.academic_year,
            is_current=True,
        )
        self.course = Course.objects.create(name="Introduction to Programming")
        self.semester.courses.add(self.course)
        self.lecturer = User.objects.create_user(
            username="lecturer",
            password="password123",
            is_lecturer=True,
        )
        self.student_user = User.objects.create_user(
            username="student",
            password="password123",
            first_name="Jane",
            last_name="Smith",
        )
        self.student = Student.objects.create(
            student=self.student_user,
            group=self.group,
        )
        self.first_grade = Grade_1st_module.objects.create(
            lecturer=self.lecturer,
            student=self.student,
            course=self.course,
            attendance=Decimal("20.00"),
            activities=Decimal("25.00"),
            exam=Decimal("30.00"),
            total=Decimal("75.00"),
            grade="B+",
        )
        Grade_2nd_module.objects.create(
            lecturer=self.lecturer,
            student=self.student,
            course=self.course,
        )
        Grade_semester.objects.create(
            lecturer=self.lecturer,
            student=self.student,
            course=self.course,
            semester=self.semester,
        )

    def test_unauthenticated_bulk_update_is_rejected(self):
        response = self.client.post(
            reverse("lecturer-bulk-grades-bulk-update"),
            {"course_id": self.course.pk, "grade_type": "1st_module", "grades": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_cannot_bulk_update_grades(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.post(
            reverse("lecturer-bulk-grades-bulk-update"),
            {"course_id": self.course.pk, "grade_type": "1st_module", "grades": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_lecturer_can_bulk_update_grade(self):
        self.client.force_authenticate(self.lecturer)
        response = self.client.post(
            reverse("lecturer-bulk-grades-bulk-update"),
            {
                "course_id": self.course.pk,
                "grade_type": "1st_module",
                "grades": [{"student_id": self.student.pk, "attendance": "25.00"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.first_grade.refresh_from_db()
        self.assertEqual(self.first_grade.attendance, Decimal("25.00"))
        self.assertEqual(self.first_grade.total, Decimal("80.00"))

    def test_student_sees_only_own_grades(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.get(reverse("grade-1st-modules-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["student"], self.student.pk)

    def test_grade_search_uses_current_user_and_course_fields(self):
        self.client.force_authenticate(self.lecturer)
        response = self.client.get(reverse("grade-1st-modules-list"), {"search": "Jane"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_student_can_get_all_own_grades(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.get(reverse("grade-semesters-my-all-grades"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["first_module_grades"]), 1)
        self.assertEqual(len(response.data["second_module_grades"]), 1)
        self.assertEqual(len(response.data["semester_grades"]), 1)
