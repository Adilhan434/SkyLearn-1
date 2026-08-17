from rest_framework.permissions import BasePermission

from accounts.models import LMSPermissionCode, RoleCode
from courses.models import Course
from courses.permissions import courses_accessible_to, has_course_management_role


class CalendarStaffPermission(BasePermission):
    message = "Calendar management is not allowed."
    permission_by_method = {
        "GET": LMSPermissionCode.CALENDAR_VIEW,
        "POST": LMSPermissionCode.CALENDAR_MANAGE,
        "PATCH": LMSPermissionCode.CALENDAR_MANAGE,
        "PUT": LMSPermissionCode.CALENDAR_MANAGE,
        "DELETE": LMSPermissionCode.CALENDAR_MANAGE,
    }

    def has_permission(self, request, view):
        del view
        required_permission = self.permission_by_method.get(request.method)
        return bool(
            has_course_management_role(request.user)
            and required_permission
            and request.user.has_lms_permission(required_permission)
        )

    def has_object_permission(self, request, view, obj):
        del view
        return courses_accessible_to(
            request.user,
            Course.objects.filter(pk=obj.course_id),
        ).exists()


class StudentCalendarPermission(BasePermission):
    message = "Student calendar access is not allowed."

    def has_permission(self, request, view):
        del view
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.roles.filter(code=RoleCode.STUDENT).exists()
            and user.has_lms_permission(LMSPermissionCode.CALENDAR_VIEW)
        )
