from rest_framework import serializers

from accounts.models import User


class TeacherReferenceSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "full_name", "email")

    def get_email(self, obj) -> str | None:
        return obj.email or None

    def get_full_name(self, obj) -> str:
        return " ".join(filter(None, (obj.first_name, obj.last_name)))
