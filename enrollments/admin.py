from django.contrib import admin

from audit.admin import AuditAdminMixin

from .models import Enrollment, SISSyncEvent


@admin.register(Enrollment)
class EnrollmentAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = (
        "student",
        "course",
        "status",
        "source",
        "enrolled_at",
    )
    list_filter = ("status", "source", "course")
    search_fields = (
        "student__username",
        "student__email",
        "course__code",
        "course__title",
        "external_sis_id",
    )
    list_select_related = ("student", "course")
    autocomplete_fields = ("student", "course")


@admin.register(SISSyncEvent)
class SISSyncEventAdmin(admin.ModelAdmin):
    list_display = (
        "external_event_id",
        "student_external_id",
        "course_code",
        "action",
        "result",
        "processed_at",
    )
    list_filter = ("action", "result")
    search_fields = (
        "external_event_id",
        "student_external_id",
        "course_code",
    )
    list_select_related = ("enrollment", "created_by")
    readonly_fields = (
        "external_event_id",
        "student_external_id",
        "course_code",
        "action",
        "result",
        "enrollment",
        "processed_at",
        "created_by",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
