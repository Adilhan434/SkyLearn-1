from django.urls import path
from . import views

urlpatterns = [
    # Student endpoints
    path("my/", views.StudentDocumentListCreateView.as_view(), name="student-docs"),
    path("my/<int:pk>/", views.StudentDocumentDetailView.as_view(), name="student-doc-detail"),

    # Methodologist endpoints
    path("all/", views.MethodologistDocumentListView.as_view(), name="methodologist-docs"),
    path("<int:pk>/review/", views.MethodologistDocumentReviewView.as_view(), name="doc-review"),
]
