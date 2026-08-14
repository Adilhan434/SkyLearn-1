"""Object-level access policy for Release 1 course management."""

from rest_framework.permissions import BasePermission

from accounts.models import LMSPermissionCode, RoleCode
from courses.models import Course


COURSE_MANAGEMENT_ROLES = {
    RoleCode.TEACHER,
    RoleCode.TEACHING_ASSISTANT,
    RoleCode.CONTENT_MANAGER,
    RoleCode.LMS_ADMIN,
    RoleCode.SUPER_ADMIN,
}

GLOBAL_COURSE_ACCESS_ROLES = {
    RoleCode.CONTENT_MANAGER,
    RoleCode.LMS_ADMIN,
    RoleCode.SUPER_ADMIN,
}


def has_course_management_role(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.roles.filter(code__in=COURSE_MANAGEMENT_ROLES).exists()


def has_global_course_access(user):
    if user.is_superuser:
        return True
    return user.roles.filter(code__in=GLOBAL_COURSE_ACCESS_ROLES).exists()


def courses_accessible_to(user, queryset=None):
    queryset = queryset if queryset is not None else Course.objects.all()
    if (
        not has_course_management_role(user)
        or not user.has_lms_permission(LMSPermissionCode.COURSES_VIEW)
    ):
        return queryset.none()
    if has_global_course_access(user):
        return queryset
    assignment_roles = user.roles.filter(
        code__in={RoleCode.TEACHER, RoleCode.TEACHING_ASSISTANT}
    ).values_list("code", flat=True)
    return queryset.filter(
        teaching_assignments__user=user,
        teaching_assignments__role__in=assignment_roles,
    ).distinct()


class CourseAccessPermission(BasePermission):
    """Check method permission and object membership for staff Course API."""

    message = "Course access is not allowed."
    permission_by_method = {
        "GET": LMSPermissionCode.COURSES_VIEW,
        "POST": LMSPermissionCode.COURSES_CREATE,
        "PATCH": LMSPermissionCode.COURSES_EDIT,
        "PUT": LMSPermissionCode.COURSES_EDIT,
        "DELETE": LMSPermissionCode.COURSES_DELETE,
    }

    def has_permission(self, request, view):
        user = request.user
        if not has_course_management_role(user):
            return False
        permission_code = self.permission_by_method.get(request.method)
        return bool(
            permission_code and user.has_lms_permission(permission_code)
        )

    def has_object_permission(self, request, view, obj):
        return courses_accessible_to(
            request.user,
            Course.objects.filter(pk=obj.pk),
        ).exists()


class CourseLifecyclePermission(BasePermission):
    """Require an action-specific permission and course membership."""

    message = "Course lifecycle action is not allowed."

    def has_permission(self, request, view):
        user = request.user
        required_permission = getattr(view, "required_permission", None)
        return bool(
            has_course_management_role(user)
            and required_permission
            and user.has_lms_permission(required_permission)
        )

    def has_object_permission(self, request, view, obj):
        return courses_accessible_to(
            request.user,
            Course.objects.filter(pk=obj.pk),
        ).exists()


class CourseTemplatePermission(BasePermission):
    """Require every LMS permission declared by a template endpoint."""

    message = "Course template access is not allowed."

    def has_permission(self, request, view):
        user = request.user
        required_permissions = getattr(
            view,
            "required_permissions",
            (LMSPermissionCode.COURSES_COPY,),
        )
        return bool(
            has_course_management_role(user)
            and all(
                user.has_lms_permission(permission)
                for permission in required_permissions
            )
        )
