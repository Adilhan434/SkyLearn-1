from django.urls import path

from .views import (
    ArchiveCourseView,
    CourseDetailView,
    CourseListCreateView,
    CourseReadinessView,
    PublishCourseView,
    RestoreCourseView,
    ReturnForRevisionView,
    SubmitReviewView,
)


app_name = "courses-v1"

urlpatterns = [
    path("", CourseListCreateView.as_view(), name="list-create"),
    path("<int:pk>/", CourseDetailView.as_view(), name="detail"),
    path(
        "<int:pk>/readiness/",
        CourseReadinessView.as_view(),
        name="readiness",
    ),
    path(
        "<int:pk>/submit-review/",
        SubmitReviewView.as_view(),
        name="submit-review",
    ),
    path(
        "<int:pk>/return-for-revision/",
        ReturnForRevisionView.as_view(),
        name="return-for-revision",
    ),
    path("<int:pk>/publish/", PublishCourseView.as_view(), name="publish"),
    path("<int:pk>/archive/", ArchiveCourseView.as_view(), name="archive"),
    path("<int:pk>/restore/", RestoreCourseView.as_view(), name="restore"),
]
