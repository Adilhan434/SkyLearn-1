from django.urls import path

from .views import (
    DepartmentListView,
    FacultyListView,
    ProgramListView,
    SemesterListView,
)

app_name = "organization-v1"

urlpatterns = [
    path("faculties/", FacultyListView.as_view(), name="faculty-list"),
    path("departments/", DepartmentListView.as_view(), name="department-list"),
    path("programs/", ProgramListView.as_view(), name="program-list"),
    path("semesters/", SemesterListView.as_view(), name="semester-list"),
]
