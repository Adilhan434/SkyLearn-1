from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


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
                },
            }
        )
