from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from courses.models import Course, CourseStatus
from organization.models import DegreeLevel, Department, Faculty, Program, Semester


class CourseAPITests(APITestCase):
    list_url = "/api/v1/courses/"

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="course-reader",
            password="test-password",
        )
        self.staff = user_model.objects.create_user(
            username="course-admin",
            password="test-password",
            is_staff=True,
        )
        self.faculty = Faculty.objects.create(name="Engineering", code="ENG")
        self.other_faculty = Faculty.objects.create(name="Business", code="BUS")
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
        self.other_semester = Semester.objects.create(
            name="Spring 2027",
            start_date=date(2027, 1, 15),
            end_date=date(2027, 5, 30),
        )
        self.course = self.create_course()

    def create_course(self, **overrides):
        index = Course.objects.count() + 1
        values = {
            "title": f"Introduction to Programming {index}",
            "code": f"CS{index:03d}",
            "description": "Programming foundations",
            "credits": 5,
            "semester": self.semester,
            "faculty": self.faculty,
            "department": self.department,
            "program": self.program,
            "status": CourseStatus.DRAFT,
            "start_date": date(2026, 9, 1),
            "end_date": date(2026, 12, 20),
            "created_by": self.staff,
            "updated_by": self.staff,
        }
        values.update(overrides)
        return Course.objects.create(**values)

    def valid_payload(self, **overrides):
        values = {
            "title": "Data Structures",
            "code": "CS201",
            "description": "Core data structures",
            "language": "en",
            "credits": 5,
            "semester": self.semester.pk,
            "faculty": self.faculty.pk,
            "department": self.department.pk,
            "program": self.program.pk,
            "status": CourseStatus.DRAFT,
            "start_date": "2026-09-01",
            "end_date": "2026-12-20",
        }
        values.update(overrides)
        return values

    def test_list_requires_authentication(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_gets_paginated_compact_list(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data),
            {"count", "next", "previous", "results"},
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0],
            {
                "id": self.course.pk,
                "title": self.course.title,
                "code": self.course.code,
                "status": CourseStatus.DRAFT,
                "credits": 5,
            },
        )

    def test_list_is_paginated(self):
        for number in range(2, 23):
            self.create_course(code=f"CS{number:03d}")
        self.client.force_authenticate(self.user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.data["count"], 22)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])

    def test_search_matches_title_and_code(self):
        self.create_course(title="Database Systems", code="DB301")
        self.client.force_authenticate(self.user)

        title_response = self.client.get(self.list_url, {"search": "Database"})
        code_response = self.client.get(self.list_url, {"search": "DB301"})

        self.assertEqual(title_response.data["count"], 1)
        self.assertEqual(code_response.data["count"], 1)

    def test_filters_by_status_semester_and_faculty(self):
        self.create_course(
            code="CS-PUB",
            status=CourseStatus.PUBLISHED,
            semester=self.other_semester,
        )
        self.client.force_authenticate(self.user)

        status_response = self.client.get(
            self.list_url, {"status": CourseStatus.PUBLISHED}
        )
        semester_response = self.client.get(
            self.list_url, {"semester": self.other_semester.pk}
        )
        faculty_response = self.client.get(
            self.list_url, {"faculty": self.other_faculty.pk}
        )

        self.assertEqual(status_response.data["count"], 1)
        self.assertEqual(semester_response.data["count"], 1)
        self.assertEqual(faculty_response.data["count"], 0)

    def test_regular_user_cannot_create_course(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(self.list_url, self.valid_payload())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_create_course_and_is_recorded_as_creator(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(self.list_url, self.valid_payload())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Course.objects.get(code="CS201")
        self.assertEqual(created.created_by, self.staff)
        self.assertEqual(created.updated_by, self.staff)

    def test_create_validates_organization_relationships(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(
            self.list_url,
            self.valid_payload(faculty=self.other_faculty.pk),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("department", response.data["error"]["fields"])

    def test_authenticated_user_can_retrieve_course(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(f"{self.list_url}{self.course.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.course.pk)
        self.assertEqual(response.data["code"], self.course.code)

    def test_unknown_course_returns_not_found(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(f"{self.list_url}999999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_routes_have_stable_names(self):
        self.assertEqual(
            reverse("api-v1:courses-v1:list-create"),
            self.list_url,
        )
        self.assertEqual(
            reverse("api-v1:courses-v1:detail", kwargs={"pk": self.course.pk}),
            f"{self.list_url}{self.course.pk}/",
        )
