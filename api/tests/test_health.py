from unittest.mock import patch

from django.db import DatabaseError
from django.urls import resolve, reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.v1.views import HealthCheckView


class HealthCheckTests(APITestCase):
    def test_health_endpoint_checks_database_and_returns_contract(self):
        response = self.client.get("/api/v1/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "database": "ok",
                "service": "su-lms-backend",
            },
        )

    def test_health_endpoint_does_not_require_authentication(self):
        response = self.client.get(
            "/api/v1/health/",
            HTTP_AUTHORIZATION="Bearer invalid-token",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch(
        "api.v1.views.connection.cursor",
        side_effect=DatabaseError("sensitive database detail"),
    )
    def test_database_failure_returns_safe_service_unavailable(self, _cursor):
        response = self.client.get("/api/v1/health/")

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        self.assertEqual(
            response.json(),
            {
                "status": "error",
                "database": "unavailable",
                "service": "su-lms-backend",
            },
        )
        self.assertNotIn("sensitive", response.content.decode())

    def test_health_endpoint_has_stable_named_route(self):
        self.assertEqual(reverse("api-v1:health"), "/api/v1/health/")
        self.assertIs(
            resolve("/api/v1/health/").func.view_class,
            HealthCheckView,
        )
