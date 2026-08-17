from rest_framework.permissions import BasePermission

from accounts.models import LMSPermissionCode, RoleCode
from courses.models import Course, CourseStatus
from courses.permissions import courses_accessible_to, has_course_management_role
from enrollments.models import EnrollmentStatus
from learning.availability import evaluate_lesson_availability
from progress.models import LessonProgress, LessonProgressStatus


EDITABLE_STRUCTURE_STATUSES = {
    CourseStatus.DRAFT,
    CourseStatus.NEEDS_REVISION,
}


def course_content_accessible_to(user, queryset=None):
    """Courses readable through management scope or active Student access."""

    queryset = queryset if queryset is not None else Course.objects.all()
    management_courses = courses_accessible_to(user, queryset)
    if not user or not user.is_authenticated or not user.is_active:
        return management_courses
    is_student = user.roles.filter(code=RoleCode.STUDENT).exists()
    if not (is_student and user.has_lms_permission(LMSPermissionCode.COURSES_VIEW)):
        return management_courses
    student_courses = queryset.filter(
        status=CourseStatus.PUBLISHED,
        enrollments__student=user,
        enrollments__status=EnrollmentStatus.ACTIVE,
    )
    return (management_courses | student_courses).distinct()


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
    has_global_access = (
        user.is_superuser
        or user.roles.filter(
            code__in={
                RoleCode.CONTENT_MANAGER,
                RoleCode.LMS_ADMIN,
                RoleCode.SUPER_ADMIN,
            }
        ).exists()
    )
    return has_global_access or course.status in EDITABLE_STRUCTURE_STATUSES


class StructureManagePermission(BasePermission):
    message = "Course structure management is not allowed."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            has_course_management_role(user)
            and user.has_lms_permission(LMSPermissionCode.COURSE_STRUCTURE_MANAGE)
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


class MaterialPermission(BasePermission):
    """Apply material permissions together with course ownership checks."""

    message = "Learning material access is not allowed."
    permission_by_method = {
        "GET": LMSPermissionCode.MATERIALS_VIEW,
        "POST": LMSPermissionCode.MATERIALS_UPLOAD,
        "PATCH": LMSPermissionCode.MATERIALS_EDIT,
        "PUT": LMSPermissionCode.MATERIALS_EDIT,
        "DELETE": LMSPermissionCode.MATERIALS_DELETE,
    }

    def has_permission(self, request, view):
        permission_code = self.permission_by_method.get(request.method)
        user = request.user
        is_student = bool(
            user
            and user.is_authenticated
            and user.roles.filter(code=RoleCode.STUDENT).exists()
        )
        if is_student and not getattr(view, "allow_student_access", False):
            return False
        has_supported_role = has_course_management_role(user) or is_student
        return bool(
            has_supported_role
            and permission_code
            and user.has_lms_permission(permission_code)
        )

    def has_object_permission(self, request, view, obj):
        course = structure_course_for(obj)
        has_access = course_content_accessible_to(
            request.user,
            Course.objects.filter(pk=course.pk),
        ).exists()
        if request.method == "GET":
            is_student = request.user.roles.filter(code=RoleCode.STUDENT).exists()
            if is_student and hasattr(obj, "lesson"):
                completed_lesson_ids = LessonProgress.objects.filter(
                    student=request.user,
                    lesson__topic__module__course=course,
                    status=LessonProgressStatus.COMPLETED,
                ).values_list("lesson_id", flat=True)
                return bool(
                    has_access
                    and evaluate_lesson_availability(
                        obj.lesson,
                        completed_lesson_ids=completed_lesson_ids,
                    ).is_available
                )
            return has_access
        return has_access and can_edit_structure(request.user, course)
