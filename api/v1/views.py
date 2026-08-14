import logging

from django.db import DatabaseError, connection
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


logger = logging.getLogger(__name__)


class ApiV1RootView(APIView):
    """Expose the active API version and its planned resource namespaces."""

    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="api_v1_root",
        description="Return API v1 metadata and resource namespaces.",
        responses={200: dict},
    )
    def get(self, request):
        return Response(
            {
                "version": "v1",
                "resources": {
                    "auth": "/api/v1/auth/",
                    "users": "/api/v1/users/",
                    "roles": "/api/v1/roles/",
                    "organization": "/api/v1/organization/",
                    "courses": "/api/v1/courses/",
                    "course_templates": "/api/v1/course-templates/",
                    "health": "/api/v1/health/",
                },
            }
        )


class HealthCheckView(APIView):
    """Report application and database availability without authentication."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="api_v1_health",
        description="Check service and database availability.",
        responses={200: dict, 503: dict},
        tags=["System"],
    )
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            logger.warning("Database health check failed.")
            return Response(
                {
                    "status": "error",
                    "database": "unavailable",
                    "service": "su-lms-backend",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "status": "ok",
                "database": "ok",
                "service": "su-lms-backend",
            }
        )
