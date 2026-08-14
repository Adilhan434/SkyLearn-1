from django.contrib import admin

from audit.admin import AuditAdminMixin

from .models import CourseModule, CourseTopic, LearningMaterial, Lesson


@admin.register(CourseModule)
class CourseModuleAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("course", "order", "title", "release_type", "release_at")
    list_filter = ("release_type", "course")
    search_fields = ("title", "course__title", "course__code")
    list_select_related = ("course",)


@admin.register(CourseTopic)
class CourseTopicAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("module", "order", "title")
    search_fields = ("title", "module__title", "module__course__code")
    list_select_related = ("module", "module__course")


@admin.register(Lesson)
class LessonAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = (
        "topic",
        "order",
        "title",
        "lesson_type",
        "release_type",
        "is_published",
    )
    list_filter = ("lesson_type", "release_type", "is_published")
    search_fields = ("title", "topic__title", "topic__module__course__code")
    list_select_related = ("topic", "topic__module", "topic__module__course")


@admin.register(LearningMaterial)
class LearningMaterialAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "lesson",
        "type",
        "download_allowed",
        "created_at",
    )
    list_filter = ("type", "download_allowed", "course")
    search_fields = (
        "title",
        "description",
        "original_filename",
        "lesson__title",
        "course__title",
        "course__code",
    )
    list_select_related = (
        "course",
        "lesson",
        "lesson__topic",
        "lesson__topic__module",
    )
