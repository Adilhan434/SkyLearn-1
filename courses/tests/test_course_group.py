from datetime import date
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode
from courses.models import Course, CourseStatus
from courses.models import Course, CourseStatus, CourseTeachingRole
from organization.models import (
    DegreeLevel,
    Department,
    Faculty,
    Group,
    Program,
    Semester,
)


class CourseGroupAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        teacher_role, _ = Role.objects.get_or_create(code=RoleCode.TEACHER)
        cls.teacher = user_model.objects.create_user(
            username="teacher-user",
            password="test-password",
            first_name="Jane",
            last_name="Teacher",
        )
        cls.teacher.roles.add(teacher_role)

        cls.faculty = Faculty.objects.create(name="Engineering", code="ENG")
        cls.department = Department.objects.create(
            faculty=cls.faculty,
            name="Computer Science",
            code="CS",
        )
        cls.program = Program.objects.create(
            department=cls.department,
            name="Software Engineering",
            code="SE",
            degree_level=DegreeLevel.BACHELOR,
        )
        cls.other_program = Program.objects.create(
            department=cls.department,
            name="Computer Science BSc",
            code="CS-BSC",
            degree_level=DegreeLevel.BACHELOR,
        )
        cls.group = Group.objects.create(
            program=cls.program,
            name="SE-24",
            admission_year=2024,
        )
        cls.other_group = Group.objects.create(
            program=cls.other_program,
            name="CS-24",
            admission_year=2024,
        )
        cls.semester = Semester.objects.create(
            name="Fall 2026",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        cls.list_create_url = reverse("api-v1:courses-v1:list-create")

    def setUp(self):
        self.client.force_authenticate(self.teacher)

    def test_create_course_with_valid_group(self):
        payload = {
            "title": "Algorithms and Data Structures",
            "code": "CS105",
            "description": "Group specific course",
            "language": "en",
            "credits": 5,
            "semester": self.semester.pk,
            "faculty": self.faculty.pk,
            "department": self.department.pk,
            "program": self.program.pk,
            "group": self.group.pk,
            "start_date": "2026-09-01",
            "end_date": "2026-12-20",
        }
        response = self.client.post(self.list_create_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get("group"), self.group.pk)

        course = Course.objects.get(code="CS105")
        self.assertEqual(course.group, self.group)

        detail_url = reverse("api-v1:courses-v1:detail", kwargs={"pk": course.pk})
        detail_response = self.client.get(detail_url)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(detail_response.data.get("group"))
        self.assertEqual(detail_response.data["group"]["id"], self.group.pk)
        self.assertEqual(detail_response.data["group"]["name"], "SE-24")

    def test_create_course_with_mismatched_group_fails(self):
        payload = {
            "title": "Algorithms and Data Structures",
            "code": "CS106",
            "description": "Mismatched group course",
            "language": "en",
            "credits": 5,
            "semester": self.semester.pk,
            "faculty": self.faculty.pk,
            "department": self.department.pk,
            "program": self.program.pk,
            "group": self.other_group.pk,  # belongs to other_program
            "start_date": "2026-09-01",
            "end_date": "2026-12-20",
        }
        response = self.client.post(self.list_create_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("group", response.data["error"]["fields"])

    def test_filter_courses_by_group(self):
        c1 = Course.objects.create(
            title="Course For Group SE-24",
            code="SE101",
            credits=3,
            semester=self.semester,
            faculty=self.faculty,
            department=self.department,
            program=self.program,
            group=self.group,
            status=CourseStatus.DRAFT,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
            created_by=self.teacher,
            updated_by=self.teacher,
        )
        c1.teaching_assignments.create(
            user=self.teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
            created_by=self.teacher,
            updated_by=self.teacher,
        )
        c2 = Course.objects.create(
            title="Course Without Group",
            code="GEN101",
            credits=3,
            semester=self.semester,
            faculty=self.faculty,
            department=self.department,
            program=self.program,
            group=None,
            status=CourseStatus.DRAFT,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
            created_by=self.teacher,
            updated_by=self.teacher,
        )
        c2.teaching_assignments.create(
            user=self.teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
            created_by=self.teacher,
            updated_by=self.teacher,
        )

        response = self.client.get(self.list_create_url, {"group": self.group.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["code"], "SE101")
        self.assertEqual(results[0]["group"]["id"], self.group.pk)
        self.assertEqual(results[0]["group"]["name"], "SE-24")
