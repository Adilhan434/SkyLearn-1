from django.urls import path

from .reference_views import TeacherReferenceListView


app_name = "references"

urlpatterns = [
    path("teachers/", TeacherReferenceListView.as_view(), name="teacher-list"),
]
