from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from organization.models import DegreeLevel, Department, Faculty, Program, Semester


class OrganizationReferenceAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="organization-reader",
            password="test-password",
        )
        cls.faculty = Faculty.objects.create(name="Engineering", code="ENG")
        cls.other_faculty = Faculty.objects.create(name="Science", code="SCI")
        cls.inactive_faculty = Faculty.objects.create(
            name="Inactive Faculty",
            code="OLD",
            is_active=False,
        )
        cls.department = Department.objects.create(
            faculty=cls.faculty,
            name="Computer Science",
            code="CS",
        )
        cls.other_department = Department.objects.create(
            faculty=cls.other_faculty,
            name="Mathematics",
            code="MATH",
        )
        cls.inactive_department = Department.objects.create(
            faculty=cls.faculty,
            name="Inactive Department",
            code="OLD",
            is_active=False,
        )
        cls.program = Program.objects.create(
            department=cls.department,
            name="Software Engineering",
            code="SE",
            degree_level=DegreeLevel.BACHELOR,
        )
        cls.other_program = Program.objects.create(
            department=cls.other_department,
            name="Applied Mathematics",
            code="AM",
            degree_level=DegreeLevel.MASTER,
        )
        cls.inactive_program = Program.objects.create(
            department=cls.department,
            name="Inactive Program",
            code="OLD",
            degree_level=DegreeLevel.ASSOCIATE,
            is_active=False,
        )
        cls.semester = Semester.objects.create(
            name="Fall 2026",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 24),
        )
        cls.inactive_semester = Semester.objects.create(
            name="Archived Semester",
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 24),
            is_active=False,
        )

    def setUp(self):
        self.client.force_authenticate(self.user)

    def test_anonymous_requests_require_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/v1/organization/faculties/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_faculties_return_only_active_records(self):
        response = self.client.get("/api/v1/organization/faculties/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": self.faculty.id,
                    "name": "Engineering",
                    "code": "ENG",
                    "is_active": True,
                },
                {
                    "id": self.other_faculty.id,
                    "name": "Science",
                    "code": "SCI",
                    "is_active": True,
                },
            ],
        )

    def test_departments_can_be_filtered_by_faculty(self):
        response = self.client.get(
            "/api/v1/organization/departments/",
            {"faculty": self.faculty.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": self.department.id,
                    "faculty": self.faculty.id,
                    "name": "Computer Science",
                    "code": "CS",
                    "is_active": True,
                }
            ],
        )

    def test_programs_can_be_filtered_by_department(self):
        response = self.client.get(
            "/api/v1/organization/programs/",
            {"department": self.department.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": self.program.id,
                    "department": self.department.id,
                    "name": "Software Engineering",
                    "code": "SE",
                    "degree_level": "bachelor",
                    "is_active": True,
                }
            ],
        )

    def test_semesters_return_dates_and_only_active_records(self):
        response = self.client.get("/api/v1/organization/semesters/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": self.semester.id,
                    "name": "Fall 2026",
                    "start_date": "2026-09-01",
                    "end_date": "2026-12-24",
                    "is_active": True,
                }
            ],
        )

    def test_reference_endpoints_are_read_only(self):
        response = self.client.post(
            "/api/v1/organization/faculties/",
            {"name": "Business", "code": "BUS"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
