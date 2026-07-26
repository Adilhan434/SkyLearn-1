from drf_spectacular.generators import SchemaGenerator
from rest_framework import status
from rest_framework.test import APITestCase


class OpenApiTests(APITestCase):
    def test_schema_and_swagger_routes_are_available(self):
        schema_response = self.client.get("/api/schema/")
        docs_response = self.client.get("/api/docs/")

        self.assertEqual(schema_response.status_code, status.HTTP_200_OK)
        self.assertEqual(docs_response.status_code, status.HTTP_200_OK)

    def test_schema_contains_all_release1_endpoints(self):
        schema = SchemaGenerator().get_schema(request=None, public=True)

        self.assertTrue(
            {
                "/api/v1/auth/login/",
                "/api/v1/auth/logout/",
                "/api/v1/auth/refresh/",
                "/api/v1/auth/me/",
                "/api/v1/users/",
                "/api/v1/users/{id}/",
                "/api/v1/roles/",
            }.issubset(schema["paths"])
        )

    def test_schema_defines_cookie_authentication(self):
        schema = SchemaGenerator().get_schema(request=None, public=True)

        self.assertEqual(
            schema["components"]["securitySchemes"]["cookieAuth"],
            {
                "type": "apiKey",
                "in": "cookie",
                "name": "access_token",
                "description": (
                    "JWT access token stored in an httpOnly cookie."
                ),
            },
        )
