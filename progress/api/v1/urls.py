from django.urls import path

from progress.api.v1.views import (
    StudentCourseProgressView,
    StudentDashboardView,
    StudentLessonCompleteView,
    StudentLessonStartView,
    StudentProgressView,
)


app_name = "progress-v1"

urlpatterns = [
    path("dashboard/", StudentDashboardView.as_view(), name="student-dashboard"),
    path("progress/", StudentProgressView.as_view(), name="student-progress"),
    path(
        "courses/<int:pk>/progress/",
        StudentCourseProgressView.as_view(),
        name="course-progress",
    ),
    path(
        "lessons/<int:pk>/start/",
        StudentLessonStartView.as_view(),
        name="lesson-start",
    ),
    path(
        "lessons/<int:pk>/complete/",
        StudentLessonCompleteView.as_view(),
        name="lesson-complete",
    ),
]
