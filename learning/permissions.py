from rest_framework.permissions import BasePermission

from accounts.models import LMSPermissionCode, RoleCode
from courses.models import Course, CourseStatus
from courses.permissions import courses_accessible_to, has_course_management_role


EDITABLE_STRUCTURE_STATUSES = {
    CourseStatus.DRAFT,
    CourseStatus.NEEDS_REVISION,
}


def structure_course_for(obj):
    if isinstance(obj, Course):
        return obj
    if hasattr(obj, "course"):
        return obj.course
    if hasattr(obj, "module"):
        return obj.module.course
    return obj.topic.module.course


def can_edit_structure(user, course):
    if course.status == CourseStatus.ARCHIVED:
        return False
    has_global_access = user.is_superuser or user.roles.filter(
        code__in={
            RoleCode.CONTENT_MANAGER,
            RoleCode.LMS_ADMIN,
            RoleCode.SUPER_ADMIN,
        }
    ).exists()
    return has_global_access or course.status in EDITABLE_STRUCTURE_STATUSES


class StructureManagePermission(BasePermission):
    message = "Course structure management is not allowed."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            has_course_management_role(user)
            and user.has_lms_permission(
                LMSPermissionCode.COURSE_STRUCTURE_MANAGE
            )
        )

    def has_object_permission(self, request, view, obj):
        course = structure_course_for(obj)
        has_access = courses_accessible_to(
            request.user,
            Course.objects.filter(pk=course.pk),
        ).exists()
        return has_access and can_edit_structure(request.user, course)


class StructureObjectPermission(BasePermission):
    """Allow structure reads and require manage permission for writes."""

    message = "Course structure access is not allowed."

    def has_permission(self, request, view):
        user = request.user
        permission_code = (
            LMSPermissionCode.COURSE_STRUCTURE_VIEW
            if request.method == "GET"
            else LMSPermissionCode.COURSE_STRUCTURE_MANAGE
        )
        return bool(
            has_course_management_role(user)
            and user.has_lms_permission(permission_code)
        )

    def has_object_permission(self, request, view, obj):
        course = structure_course_for(obj)
        has_access = courses_accessible_to(
            request.user,
            Course.objects.filter(pk=course.pk),
        ).exists()
        if request.method == "GET":
            return has_access
        return has_access and can_edit_structure(request.user, course)
