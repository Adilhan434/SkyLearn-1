from django.urls import path

from .integration_views import SISEnrollmentSyncView


app_name = "sis-integration-v1"

urlpatterns = [
    path(
        "enrollments/sync/",
        SISEnrollmentSyncView.as_view(),
        name="enrollment-sync",
    ),
]
