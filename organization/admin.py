from django.contrib import admin

from audit.admin import AuditAdminMixin

from .models import Department, Faculty, Group, Program, Semester


@admin.register(Faculty)
class FacultyAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Department)
class DepartmentAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("code", "name", "faculty", "is_active", "updated_at")
    list_filter = ("is_active", "faculty")
    search_fields = ("code", "name", "faculty__name", "faculty__code")
    list_select_related = ("faculty",)


@admin.register(Program)
class ProgramAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "department",
        "degree_level",
        "is_active",
        "updated_at",
    )
    list_filter = ("degree_level", "is_active", "department__faculty")
    search_fields = ("code", "name", "department__name")
    list_select_related = ("department",)


@admin.register(Group)
class GroupAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("name", "program", "admission_year", "is_active")
    list_filter = ("admission_year", "is_active", "program")
    search_fields = ("name", "program__name", "program__code")
    list_select_related = ("program",)


@admin.register(Semester)
class SemesterAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
