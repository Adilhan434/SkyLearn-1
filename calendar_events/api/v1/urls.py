from django.urls import path

from calendar_events.api.v1.views import (
    CalendarEventDetailView,
    CalendarEventListCreateView,
)


app_name = "calendar-v1"

urlpatterns = [
    path("events/", CalendarEventListCreateView.as_view(), name="event-list-create"),
    path("events/<int:pk>/", CalendarEventDetailView.as_view(), name="event-detail"),
]
