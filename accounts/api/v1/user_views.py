from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.filters import SearchFilter

from accounts.models import User

from .filters import UserFilter
from .pagination import UserPagination
from .permissions import IsLMSAdminOrSuperAdmin
from .user_serializers import UserCreateSerializer, UserReadSerializer


@extend_schema_view(get=extend_schema(tags=["Users"]))
class UserListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.prefetch_related("roles").order_by("id")
    permission_classes = [IsLMSAdminOrSuperAdmin]
    pagination_class = UserPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = UserFilter
    search_fields = ["email", "first_name", "last_name", "username"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UserCreateSerializer
        return UserReadSerializer

    @extend_schema(
        request=UserCreateSerializer,
        responses={201: UserReadSerializer},
        tags=["Users"],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@extend_schema_view(get=extend_schema(tags=["Users"]))
class UserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.prefetch_related("roles")
    serializer_class = UserReadSerializer
    permission_classes = [IsLMSAdminOrSuperAdmin]
