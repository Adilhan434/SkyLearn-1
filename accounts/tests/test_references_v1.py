from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode, User


class ReferenceApiV1Tests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.content_manager = User.objects.create_user(
            username="content-reference",
            email="content.reference@su.edu.kg",
        )
        cls.content_manager.roles.add(
            Role.objects.get(code=RoleCode.CONTENT_MANAGER)
        )
        cls.student = User.objects.create_user(username="student-reference")
        cls.student.roles.add(Role.objects.get(code=RoleCode.STUDENT))
        cls.teacher = User.objects.create_user(
            username="teacher-reference",
            email="teacher.reference@su.edu.kg",
            first_name="Teacher",
            last_name="Reference",
        )
        cls.teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        cls.inactive_teacher = User.objects.create_user(
            username="inactive-reference",
            email="inactive.reference@su.edu.kg",
            first_name="Inactive",
            last_name="Teacher",
            is_active=False,
        )
        cls.inactive_teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))

    def url(self):
        return reverse("api-v1:references:teacher-list")

    def test_teacher_reference_requires_authentication(self):
        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_role_without_course_create_permission_is_forbidden(self):
        self.client.force_authenticate(self.student)

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_content_manager_receives_compact_active_teacher_list(self):
        self.client.force_authenticate(self.content_manager)

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": self.teacher.pk,
                    "full_name": "Teacher Reference",
                    "email": "teacher.reference@su.edu.kg",
                }
            ],
        )

    def test_teacher_reference_route_is_stable(self):
        self.assertEqual(self.url(), "/api/v1/references/teachers/")
