from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics

from calendar_events.api.v1.filters import CalendarEventFilter
from calendar_events.api.v1.pagination import CalendarEventPagination
from calendar_events.api.v1.serializers import (
    CalendarEventSerializer,
    StudentCalendarEventSerializer,
)
from calendar_events.models import CalendarEvent
from calendar_events.permissions import (
    CalendarStaffPermission,
    StudentCalendarPermission,
)
from calendar_events.querysets import (
    staff_calendar_events,
    student_calendar_events,
)


class CalendarEventListCreateView(generics.ListCreateAPIView):
    queryset = CalendarEvent.objects.none()
    serializer_class = CalendarEventSerializer
    permission_classes = (CalendarStaffPermission,)
    pagination_class = CalendarEventPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = CalendarEventFilter

    def get_queryset(self):
        return staff_calendar_events(self.request.user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class CalendarEventDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CalendarEvent.objects.none()
    serializer_class = CalendarEventSerializer
    permission_classes = (CalendarStaffPermission,)
    http_method_names = ("get", "patch", "delete", "head", "options")

    def get_queryset(self):
        return staff_calendar_events(self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class StudentCalendarEventListView(generics.ListAPIView):
    queryset = CalendarEvent.objects.none()
    serializer_class = StudentCalendarEventSerializer
    permission_classes = (StudentCalendarPermission,)
    pagination_class = CalendarEventPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = CalendarEventFilter

    def get_queryset(self):
        return student_calendar_events(self.request.user)
