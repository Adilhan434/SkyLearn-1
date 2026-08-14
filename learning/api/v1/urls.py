from django.urls import path

from .views import (
    CourseModuleDetailView,
    CourseTopicCreateView,
    CourseTopicDetailView,
    LessonCreateView,
    LessonDetailView,
    LearningMaterialDetailView,
    LearningMaterialDownloadView,
    LearningMaterialPlaybackView,
    LessonMaterialListCreateView,
    LessonScormPackageListCreateView,
    ScormPackageContentView,
    ScormPackageDetailView,
)


app_name = "learning-v1"

urlpatterns = [
    path("modules/<int:pk>/", CourseModuleDetailView.as_view(), name="module-detail"),
    path(
        "modules/<int:module_pk>/topics/",
        CourseTopicCreateView.as_view(),
        name="topic-create",
    ),
    path("topics/<int:pk>/", CourseTopicDetailView.as_view(), name="topic-detail"),
    path(
        "topics/<int:topic_pk>/lessons/",
        LessonCreateView.as_view(),
        name="lesson-create",
    ),
    path("lessons/<int:pk>/", LessonDetailView.as_view(), name="lesson-detail"),
    path(
        "lessons/<int:lesson_pk>/materials/",
        LessonMaterialListCreateView.as_view(),
        name="lesson-material-list-create",
    ),
    path(
        "materials/<int:pk>/",
        LearningMaterialDetailView.as_view(),
        name="material-detail",
    ),
    path(
        "materials/<int:pk>/download/",
        LearningMaterialDownloadView.as_view(),
        name="material-download",
    ),
    path(
        "materials/<int:pk>/playback/",
        LearningMaterialPlaybackView.as_view(),
        name="material-playback",
    ),
    path(
        "lessons/<int:lesson_pk>/scorm-packages/",
        LessonScormPackageListCreateView.as_view(),
        name="lesson-scorm-list-create",
    ),
    path(
        "scorm-packages/<int:pk>/",
        ScormPackageDetailView.as_view(),
        name="scorm-detail",
    ),
    path(
        "scorm-packages/<int:pk>/content/<path:path>",
        ScormPackageContentView.as_view(),
        name="scorm-content",
    ),
]
