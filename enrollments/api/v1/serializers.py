from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.models import RoleCode
from enrollments.models import Enrollment


class EnrollmentSerializer(serializers.ModelSerializer):
    student = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.all(),
    )
    course = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    updated_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Enrollment
        validators = []
        fields = (
            "id",
            "student",
            "course",
            "status",
            "source",
            "external_sis_id",
            "enrolled_at",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "course",
            "status",
            "enrolled_at",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )

    def validate_student(self, student):
        if not student.is_active:
            raise serializers.ValidationError("Student must be active.")
        if not student.roles.filter(code=RoleCode.STUDENT).exists():
            raise serializers.ValidationError(
                "Selected user must have the student role."
            )
        return student
