from django.urls import path

from calendar_events.api.v1.views import StudentCalendarEventListView


app_name = "student-calendar-v1"

urlpatterns = [
    path("calendar/", StudentCalendarEventListView.as_view(), name="event-list"),
]
