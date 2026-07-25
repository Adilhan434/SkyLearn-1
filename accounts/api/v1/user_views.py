from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.filters import SearchFilter

from accounts.models import User

from .filters import UserFilter
from .pagination import UserPagination
from .permissions import IsLMSAdminOrSuperAdmin
from .user_serializers import UserCreateSerializer, UserReadSerializer


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
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class UserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.prefetch_related("roles")
    serializer_class = UserReadSerializer
    permission_classes = [IsLMSAdminOrSuperAdmin]
