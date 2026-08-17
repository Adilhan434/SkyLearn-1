from django.contrib import admin

from audit.models import CourseHistoryEvent


class AuditAdminMixin:
    """Populate audit users for models edited through Django Admin."""

    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.created_by_id:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CourseHistoryEvent)
class CourseHistoryEventAdmin(admin.ModelAdmin):
    list_display = (
        "action",
        "course",
        "object_type",
        "object_title",
        "actor",
        "created_at",
    )
    list_filter = ("action", "object_type", "created_at")
    search_fields = ("course__code", "course__title", "object_title")
    list_select_related = ("course", "actor")
    readonly_fields = (
        "course",
        "action",
        "actor",
        "object_type",
        "object_id",
        "object_title",
        "details",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
