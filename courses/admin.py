from django.contrib import admin

from audit.admin import AuditAdminMixin

from .models import Course, CourseStatus


@admin.register(Course)
class CourseAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = (
        "code",
        "title",
        "status",
        "credits",
        "semester",
        "faculty",
        "is_archived",
    )
    list_filter = ("status", "language", "semester", "faculty")
    search_fields = ("code", "title")
    list_select_related = ("semester", "faculty", "department", "program")
    @admin.display(boolean=True, description="Archived")
    def is_archived(self, obj):
        return obj.status == CourseStatus.ARCHIVED

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.status == CourseStatus.ARCHIVED:
            return False
        return super().has_change_permission(request, obj)
