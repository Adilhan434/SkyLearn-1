from django.urls import resolve, reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.v1.views import ApiV1RootView


class ApiV1RoutingTests(APITestCase):
    def test_api_v1_root_is_public_and_returns_version_metadata(self):
        response = self.client.get("/api/v1/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "version": "v1",
                "resources": {
                    "auth": "/api/v1/auth/",
                    "users": "/api/v1/users/",
                    "roles": "/api/v1/roles/",
                    "organization": "/api/v1/organization/",
                    "courses": "/api/v1/courses/",
                    "course_templates": "/api/v1/course-templates/",
                    "student": "/api/v1/student/",
                    "calendar": "/api/v1/calendar/",
                    "integrations": "/api/v1/integrations/",
                    "health": "/api/v1/health/",
                },
            },
        )

    def test_all_expected_v1_resource_prefixes_are_mounted(self):
        from api.v1.urls import urlpatterns

        mounted_prefixes = {str(pattern.pattern) for pattern in urlpatterns}

        self.assertTrue(
            {
                "auth/",
                "users/",
                "roles/",
                "organization/",
                "courses/",
                "course-templates/",
                "student/",
                "calendar/",
                "integrations/sis/",
                "health/",
            }.issubset(mounted_prefixes)
        )

    def test_api_v1_root_has_a_stable_named_route(self):
        self.assertEqual(reverse("api-v1:root"), "/api/v1/")
        self.assertIs(resolve("/api/v1/").func.view_class, ApiV1RootView)

    def test_unknown_api_v1_endpoint_returns_not_found(self):
        response = self.client.get("/api/v1/unknown/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()["error"]["code"], "not_found")

    def test_legacy_auth_endpoint_remains_registered(self):
        response = self.client.get("/accounts/token/")

        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_legacy_course_endpoint_remains_registered(self):
        response = self.client.get("/api/courses/")

        self.assertNotEqual(response.status_code, status.HTTP_404_NOT_FOUND)
