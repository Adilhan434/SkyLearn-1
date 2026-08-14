from django.contrib import admin

from audit.admin import AuditAdminMixin

from .models import Enrollment


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
