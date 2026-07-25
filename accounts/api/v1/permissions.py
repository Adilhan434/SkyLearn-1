from rest_framework.permissions import BasePermission

from accounts.models import RoleCode


class IsLMSAdminOrSuperAdmin(BasePermission):
    message = "LMS administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        return user.roles.filter(
            code__in=[RoleCode.LMS_ADMIN, RoleCode.SUPER_ADMIN]
        ).exists()
