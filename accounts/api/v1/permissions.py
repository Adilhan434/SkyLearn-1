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


class HasLMSPermission(BasePermission):
    """Require the permission code declared by the API view."""

    message = "The required LMS permission is missing."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        permission_code = getattr(view, "required_lms_permission", None)
        if not permission_code:
            raise RuntimeError(
                "HasLMSPermission requires view.required_lms_permission."
            )
        return user.has_lms_permission(permission_code)
