from django.contrib import admin
from .models import Parent, Role, Student, User, UserRole


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 0
    autocomplete_fields = ["role"]


class UserAdmin(admin.ModelAdmin):
    inlines = [UserRoleInline]
    list_display = [
        "get_full_name",
        "username",
        "email",
        "is_active",
        "is_student",
        "is_lecturer",
        "is_parent",
        "is_staff",
    ]
    search_fields = [
        "username",
        "first_name",
        "last_name",
        "email",
        "is_active",
        "is_lecturer",
        "is_parent",
        "is_staff",
    ]

    class Meta:
        managed = True
        verbose_name = "User"
        verbose_name_plural = "Users"


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["code", "name"]
    search_fields = ["code", "name"]


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "assigned_at"]
    list_filter = ["role"]
    search_fields = ["user__username", "user__email", "role__code"]
    autocomplete_fields = ["user", "role"]


admin.site.register(User, UserAdmin)
admin.site.register(Student)
admin.site.register(Parent)
