from django.contrib import admin

from audit.admin import AuditAdminMixin

from .models import Course, CourseStatus, CourseTeachingAssignment


class CourseTeachingAssignmentInline(admin.TabularInline):
    model = CourseTeachingAssignment
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Course)
class CourseAdmin(AuditAdminMixin, admin.ModelAdmin):
    inlines = (CourseTeachingAssignmentInline,)
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


@admin.register(CourseTeachingAssignment)
class CourseTeachingAssignmentAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("course", "user", "role", "is_primary", "created_at")
    list_filter = ("role", "is_primary")
    search_fields = (
        "course__code",
        "course__title",
        "user__username",
        "user__email",
    )
    autocomplete_fields = ("course", "user")
    list_select_related = ("course", "user")
