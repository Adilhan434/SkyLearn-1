from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework.views import APIView

from api.v1.exceptions import api_exception_handler


class RuntimeErrorView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        raise RuntimeError("sensitive internal detail")


class ApiErrorFormatTests(APITestCase):
    def call_handler(self, exception):
        request = APIRequestFactory().get("/api/v1/test/")
        return api_exception_handler(exception, {"request": request})

    def test_validation_error_format(self):
        response = self.call_handler(
            ValidationError({"email": ["This field is required."]})
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {
                "error": {
                    "code": "validation_error",
                    "message": "Validation failed.",
                    "fields": {
                        "email": ["This field is required."],
                    },
                }
            },
        )

    def test_unauthorized_error_format(self):
        response = self.call_handler(NotAuthenticated())

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            set(response.data["error"]),
            {"code", "message", "fields"},
        )
        self.assertEqual(
            response.data["error"]["code"],
            "authentication_required",
        )

    def test_invalid_authentication_has_distinct_error_code(self):
        response = self.call_handler(AuthenticationFailed())

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "authentication_failed")

    def test_forbidden_error_format(self):
        response = self.call_handler(PermissionDenied())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["error"]["code"], "permission_denied")
        self.assertEqual(response.data["error"]["fields"], {})

    def test_not_found_error_format(self):
        response = self.call_handler(Http404())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "not_found")

    def test_unhandled_exception_returns_safe_500(self):
        request = APIRequestFactory().get("/api/v1/test/runtime-error/")

        response = RuntimeErrorView.as_view()(request)

        self.assertEqual(
            response.status_code,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        self.assertEqual(
            response.data,
            {
                "error": {
                    "code": "internal_server_error",
                    "message": "An internal server error occurred.",
                    "fields": {},
                }
            },
        )
        self.assertNotIn("sensitive internal detail", str(response.data))

    def test_unmatched_v1_route_returns_json_error(self):
        response = self.client.get("/api/v1/not-a-real-route/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.json(),
            {
                "error": {
                    "code": "not_found",
                    "message": "Resource not found.",
                    "fields": {},
                }
            },
        )
