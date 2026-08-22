from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics

from accounts.api.v1.permissions import HasLMSPermission
from accounts.models import LMSPermissionCode, RoleCode, User

from .reference_serializers import TeacherReferenceSerializer


@extend_schema_view(
    get=extend_schema(
        tags=["References"],
        description=(
            "Return active teachers for authenticated users allowed to create "
            "courses. This compact endpoint does not expose user administration."
        ),
    )
)
class TeacherReferenceListView(generics.ListAPIView):
    serializer_class = TeacherReferenceSerializer
    permission_classes = [HasLMSPermission]
    required_lms_permission = LMSPermissionCode.COURSES_CREATE
    pagination_class = None

    def get_queryset(self):
        return (
            User.objects.filter(
                is_active=True,
                roles__code=RoleCode.TEACHER,
            )
            .distinct()
            .order_by("first_name", "last_name", "id")
        )
