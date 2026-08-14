from django.urls import include, path

from .views import ApiV1RootView, HealthCheckView


app_name = "api-v1"

urlpatterns = [
    path("", ApiV1RootView.as_view(), name="root"),
    path("health/", HealthCheckView.as_view(), name="health"),
    path("auth/", include("accounts.api.v1.auth_urls")),
    path("users/", include("accounts.api.v1.user_urls")),
    path("roles/", include("accounts.api.v1.role_urls")),
    path("organization/", include("core.api.v1.organization_urls")),
    path("student/", include("enrollments.api.v1.student_urls")),
    path(
        "integrations/sis/",
        include("enrollments.api.v1.integration_urls"),
    ),
    path("", include("learning.api.v1.urls")),
    path("courses/", include("courses.api.v1.urls")),
    path(
        "course-templates/",
        include("courses.api.v1.template_urls"),
    ),
]
