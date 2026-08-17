from django.contrib import admin

from progress.models import LessonProgress


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "lesson",
        "status",
        "started_at",
        "completed_at",
        "updated_at",
    )
    list_filter = ("status",)
    search_fields = (
        "student__username",
        "student__email",
        "lesson__title",
    )
    list_select_related = (
        "student",
        "lesson",
        "lesson__topic",
        "lesson__topic__module",
        "lesson__topic__module__course",
    )
    autocomplete_fields = ("student", "lesson")
    readonly_fields = ("updated_at",)
