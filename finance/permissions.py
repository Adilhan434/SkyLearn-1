from rest_framework import permissions


class IsStudentOrParent(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_student or request.user.is_parent)
        )

class IsAccountant(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_accountant or request.user.is_superuser)
        )
