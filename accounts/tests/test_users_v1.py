from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode, User


class UserApiV1Tests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lms_admin = User.objects.create_user(
            username="lms-admin",
            email="lms-admin@su.edu.kg",
        )
        cls.lms_admin.roles.add(
            Role.objects.get(code=RoleCode.LMS_ADMIN)
        )

        cls.super_admin = User.objects.create_user(
            username="super-admin-role",
        )
        cls.super_admin.roles.add(
            Role.objects.get(code=RoleCode.SUPER_ADMIN)
        )

        cls.student = User.objects.create_user(
            username="student-one",
            email="student.one@su.edu.kg",
            first_name="Alice",
            last_name="Example",
        )
        cls.student.roles.add(Role.objects.get(code=RoleCode.STUDENT))

        cls.inactive_teacher = User.objects.create_user(
            username="inactive-teacher",
            email="inactive.teacher@su.edu.kg",
            first_name="Bob",
            last_name="Teacher",
            is_active=False,
        )
        cls.inactive_teacher.roles.add(
            Role.objects.get(code=RoleCode.TEACHER)
        )

    def authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.lms_admin)

    def test_list_requires_authentication(self):
        response = self.client.get(reverse("api-v1:users:list-create"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_admin_role_cannot_access_list(self):
        self.authenticate(self.student)

        response = self.client.get(reverse("api-v1:users:list-create"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_lms_admin_receives_paginated_user_list(self):
        self.authenticate()

        response = self.client.get(
            reverse("api-v1:users:list-create"),
            {"page_size": 2},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 4)
        self.assertEqual(len(response.json()["results"]), 2)
        self.assertIn("next", response.json())
        self.assertIn("previous", response.json())

    def test_super_admin_role_can_retrieve_user(self):
        self.authenticate(self.super_admin)

        response = self.client.get(
            reverse("api-v1:users:detail", args=[self.student.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["id"], self.student.pk)
        self.assertEqual(response.json()["roles"], ["student"])

    def test_missing_user_returns_not_found(self):
        self.authenticate()

        response = self.client.get(
            reverse("api-v1:users:detail", args=[999999])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_search_supports_email_and_full_name(self):
        self.authenticate()
        url = reverse("api-v1:users:list-create")

        email_response = self.client.get(
            url,
            {"search": "student.one@su.edu.kg"},
        )
        name_response = self.client.get(
            url,
            {"search": "Alice Example"},
        )

        self.assertEqual(email_response.json()["count"], 1)
        self.assertEqual(name_response.json()["count"], 1)
        self.assertEqual(
            name_response.json()["results"][0]["id"],
            self.student.pk,
        )

    def test_filter_by_role(self):
        self.authenticate()

        response = self.client.get(
            reverse("api-v1:users:list-create"),
            {"role": RoleCode.TEACHER},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(
            response.json()["results"][0]["id"],
            self.inactive_teacher.pk,
        )

    def test_filter_by_activity(self):
        self.authenticate()

        response = self.client.get(
            reverse("api-v1:users:list-create"),
            {"is_active": "false"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 1)
        self.assertFalse(response.json()["results"][0]["is_active"])

    def test_admin_can_create_user_with_roles_and_hashed_password(self):
        self.authenticate()

        response = self.client.post(
            reverse("api-v1:users:list-create"),
            {
                "email": "Teacher.New@su.edu.kg",
                "first_name": "Teacher",
                "last_name": "New",
                "password": "Temporary123!",
                "roles": [RoleCode.TEACHER],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", response.json())
        self.assertEqual(response.json()["email"], "teacher.new@su.edu.kg")
        self.assertEqual(response.json()["roles"], ["teacher"])

        user = User.objects.get(email="teacher.new@su.edu.kg")
        self.assertTrue(user.check_password("Temporary123!"))
        self.assertNotEqual(user.password, "Temporary123!")
        self.assertTrue(user.is_lecturer)

    def test_create_rejects_duplicate_email_case_insensitively(self):
        self.authenticate()

        response = self.client.post(
            reverse("api-v1:users:list-create"),
            {
                "email": "STUDENT.ONE@su.edu.kg",
                "first_name": "Duplicate",
                "last_name": "Student",
                "password": "Temporary123!",
                "roles": [RoleCode.STUDENT],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json()["error"]["code"],
            "validation_error",
        )
        self.assertIn("email", response.json()["error"]["fields"])
        self.assertEqual(
            User.objects.filter(email__iexact="student.one@su.edu.kg").count(),
            1,
        )

    def test_create_rejects_unknown_role_without_creating_user(self):
        self.authenticate()

        response = self.client.post(
            reverse("api-v1:users:list-create"),
            {
                "email": "unknown.role@su.edu.kg",
                "first_name": "Unknown",
                "last_name": "Role",
                "password": "Temporary123!",
                "roles": ["unknown_role"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            User.objects.filter(email="unknown.role@su.edu.kg").exists()
        )
