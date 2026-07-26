from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode, User


class RoleApiV1Tests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lms_admin = User.objects.create_user(username="role-admin")
        cls.lms_admin.roles.add(
            Role.objects.get(code=RoleCode.LMS_ADMIN)
        )
        cls.student = User.objects.create_user(username="role-student")
        cls.student.roles.add(Role.objects.get(code=RoleCode.STUDENT))

    def test_roles_require_authentication(self):
        response = self.client.get(reverse("api-v1:roles:list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_admin_cannot_list_roles(self):
        self.client.force_authenticate(self.student)

        response = self.client.get(reverse("api-v1:roles:list"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_lms_admin_can_list_all_release1_roles(self):
        self.client.force_authenticate(self.lms_admin)

        response = self.client.get(reverse("api-v1:roles:list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertSetEqual(
            {item["code"] for item in response.json()},
            set(RoleCode.values),
        )
        self.assertTrue(
            all(
                set(item) == {"code", "name", "description"}
                for item in response.json()
            )
        )
