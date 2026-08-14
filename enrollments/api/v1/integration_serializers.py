from rest_framework import serializers

from enrollments.models import SISSyncAction, SISSyncEvent


class SISSyncRequestSerializer(serializers.Serializer):
    external_event_id = serializers.CharField(max_length=255, allow_blank=False)
    student_external_id = serializers.CharField(max_length=30, allow_blank=False)
    course_code = serializers.CharField(max_length=50, allow_blank=False)
    action = serializers.ChoiceField(choices=SISSyncAction.choices)

    def validate_external_event_id(self, value):
        return value.strip()

    def validate_student_external_id(self, value):
        return value.strip()

    def validate_course_code(self, value):
        return value.strip().upper()


class SISSyncResponseSerializer(serializers.ModelSerializer):
    enrollment = serializers.PrimaryKeyRelatedField(read_only=True)
    idempotent_replay = serializers.SerializerMethodField()

    class Meta:
        model = SISSyncEvent
        fields = (
            "external_event_id",
            "student_external_id",
            "course_code",
            "action",
            "result",
            "enrollment",
            "processed_at",
            "idempotent_replay",
        )

    def get_idempotent_replay(self, obj) -> bool:
        del obj
        return self.context.get("idempotent_replay", False)
