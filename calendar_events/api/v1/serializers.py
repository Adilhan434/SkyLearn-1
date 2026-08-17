from rest_framework import serializers

from calendar_events.models import CalendarEvent
from courses.models import Course
from courses.permissions import courses_accessible_to


class CalendarEventSerializer(serializers.ModelSerializer):
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.none())
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    updated_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = CalendarEvent
        fields = (
            "id",
            "course",
            "title",
            "description",
            "event_type",
            "start_at",
            "end_at",
            "is_public",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            fields["course"].queryset = courses_accessible_to(request.user)
        return fields

    def validate(self, attrs):
        start_at = attrs.get("start_at", getattr(self.instance, "start_at", None))
        end_at = attrs.get("end_at", getattr(self.instance, "end_at", None))
        if end_at is not None and start_at is not None and end_at < start_at:
            raise serializers.ValidationError(
                {"end_at": "Event end cannot be before its start."}
            )
        return attrs


class StudentCalendarEventSerializer(serializers.ModelSerializer):
    course_id = serializers.IntegerField(read_only=True)
    course_code = serializers.CharField(source="course.code", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)

    class Meta:
        model = CalendarEvent
        fields = (
            "id",
            "course_id",
            "course_code",
            "course_title",
            "title",
            "description",
            "event_type",
            "start_at",
            "end_at",
        )
