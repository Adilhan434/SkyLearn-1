from django.urls import reverse
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.authentication import JWTCookieAuthentication
from accounts.models import Group, Role, RoleCode, Student, User
from core.models import Program


class AuthV1Tests(APITestCase):
    password = "Demo123!"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="student-demo",
            email="student@su.edu.kg",
            first_name="Student",
            last_name="Demo",
            password=cls.password,
        )
        cls.user.roles.add(Role.objects.get(code=RoleCode.STUDENT))
        program = Program.objects.create(name="Computer Science")
        group = Group.objects.create(name="CS-22-24", program=program)
        Student.objects.create(
            student=cls.user,
            id_number="SU-2024-0012",
            group=group,
        )

    def login(self, login="student@su.edu.kg", password=None):
        return self.client.post(
            reverse("api-v1:auth:login"),
            {
                "login": login,
                "password": password or self.password,
            },
            format="json",
        )

    def test_login_by_email_sets_httponly_cookies(self):
        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "user": {
                    "id": self.user.pk,
                    "email": "student@su.edu.kg",
                    "full_name": "Student Demo",
                    "roles": ["student"],
                }
            },
        )
        self.assertNotIn("access", response.json())
        self.assertNotIn("refresh", response.json())
        self.assertTrue(response.cookies["access_token"]["httponly"])
        self.assertTrue(response.cookies["refresh_token"]["httponly"])

    def test_login_also_accepts_username(self):
        response = self.login(login=self.user.username)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_credentials_return_unauthorized(self):
        response = self.login(password="incorrect-password")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_login_field_returns_bad_request(self):
        response = self.client.post(
            reverse("api-v1:auth:login"),
            {"password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_me_requires_authentication(self):
        response = self.client.get(reverse("api-v1:auth:me"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_stable_user_contract_from_access_cookie(self):
        self.login()

        response = self.client.get(reverse("api-v1:auth:me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "id": self.user.pk,
                "email": "student@su.edu.kg",
                "first_name": "Student",
                "last_name": "Demo",
                "full_name": "Student Demo",
                "is_active": True,
                "roles": ["student"],
                "permissions": [
                    "calendar.view",
                    "course_structure.view",
                    "courses.view",
                    "materials.view",
                ],
                "profile": {
                    "student_id": "SU-2024-0012",
                    "group": "CS-22-24",
                },
            },
        )

    def test_me_returns_all_roles_in_stable_order(self):
        self.user.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.login()

        response = self.client.get(reverse("api-v1:auth:me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["roles"], ["student", "teacher"])
        self.assertIn("courses.edit", response.json()["permissions"])
        self.assertEqual(
            response.json()["permissions"],
            sorted(response.json()["permissions"]),
        )

    def test_me_allows_missing_email_and_non_student_profile(self):
        user = User.objects.create_user(
            username="teacher-without-email",
            first_name="Teacher",
            last_name="Demo",
        )
        user.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("api-v1:auth:me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.json()["email"])
        self.assertIsNone(response.json()["profile"])
        self.assertEqual(response.json()["roles"], ["teacher"])

    def test_me_keeps_nullable_student_profile_fields_stable(self):
        user = User.objects.create_user(username="student-without-details")
        user.roles.add(Role.objects.get(code=RoleCode.STUDENT))
        Student.objects.create(student=user)
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("api-v1:auth:me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()["profile"],
            {"student_id": None, "group": None},
        )

    def test_refresh_rotates_refresh_cookie_and_sets_access_cookie(self):
        login_response = self.login()
        old_refresh = login_response.cookies["refresh_token"].value

        response = self.client.post(reverse("api-v1:auth:refresh"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)
        self.assertNotEqual(
            response.cookies["refresh_token"].value,
            old_refresh,
        )
        self.assertNotIn("access", response.json())
        self.assertNotIn("refresh", response.json())

    def test_refresh_without_cookie_returns_unauthorized(self):
        response = self.client.post(reverse("api-v1:auth:refresh"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_clears_cookies_and_blacklists_refresh_token(self):
        login_response = self.login()
        refresh_token = login_response.cookies["refresh_token"].value

        response = self.client.post(reverse("api-v1:auth:logout"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.cookies["access_token"]["max-age"], 0)
        self.assertEqual(response.cookies["refresh_token"]["max-age"], 0)

        self.client.cookies["refresh_token"] = refresh_token
        refresh_response = self.client.post(reverse("api-v1:auth:refresh"))
        self.assertEqual(
            refresh_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_logout_is_idempotent_without_tokens(self):
        response = self.client.post(reverse("api-v1:auth:logout"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cookie_authentication_is_registered_for_openapi(self):
        extension = OpenApiAuthenticationExtension.get_match(
            JWTCookieAuthentication()
        )

        self.assertIsNotNone(extension)
        self.assertEqual(extension.name, "cookieAuth")
        self.assertEqual(
            extension.get_security_definition(None),
            {
                "type": "apiKey",
                "in": "cookie",
                "name": "access_token",
                "description": (
                    "JWT access token stored in an httpOnly cookie."
                ),
            },
        )
