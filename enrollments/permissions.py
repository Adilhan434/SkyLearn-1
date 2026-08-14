from rest_framework.permissions import BasePermission

from accounts.models import LMSPermissionCode
from courses.permissions import has_course_management_role


class EnrollmentPermission(BasePermission):
    """Apply method-specific Release 1 Enrollment permissions."""

    message = "Enrollment access is not allowed."
    permission_by_method = {
        "GET": LMSPermissionCode.ENROLLMENTS_VIEW,
        "POST": LMSPermissionCode.ENROLLMENTS_MANAGE,
    }

    def has_permission(self, request, view):
        user = request.user
        permission = self.permission_by_method.get(request.method)
        return bool(
            has_course_management_role(user)
            and permission
            and user.has_lms_permission(permission)
        )
