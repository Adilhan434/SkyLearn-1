from django_filters import rest_framework as filters

from calendar_events.models import CalendarEvent


class CalendarEventFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="start_at", lookup_expr="date__gte")
    date_to = filters.DateFilter(field_name="start_at", lookup_expr="date__lte")
    course = filters.NumberFilter(field_name="course_id")
    event_type = filters.CharFilter(field_name="event_type")

    class Meta:
        model = CalendarEvent
        fields = ("date_from", "date_to", "course", "event_type")
