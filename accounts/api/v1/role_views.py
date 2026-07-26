from drf_spectacular.utils import extend_schema
from rest_framework import generics

from accounts.models import Role

from .permissions import IsLMSAdminOrSuperAdmin
from .role_serializers import RoleSerializer


class RoleListView(generics.ListAPIView):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsLMSAdminOrSuperAdmin]
    pagination_class = None

    @extend_schema(tags=["Roles"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
