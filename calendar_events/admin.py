from django.contrib import admin

from audit.admin import AuditAdminMixin
from calendar_events.models import CalendarEvent


@admin.register(CalendarEvent)
class CalendarEventAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "event_type",
        "start_at",
        "end_at",
        "is_public",
    )
    list_filter = ("event_type", "is_public", "course")
    search_fields = ("title", "description", "course__title", "course__code")
    list_select_related = ("course", "created_by", "updated_by")
    autocomplete_fields = ("course",)
