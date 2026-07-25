from django.contrib.auth import authenticate
from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from accounts.models import Student, User


class LoginSerializer(serializers.Serializer):
    login = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)

    default_error_messages = {
        "invalid_credentials": "Invalid login or password.",
    }

    def validate(self, attrs):
        login = attrs["login"].strip()
        matches = User.objects.filter(
            Q(username__iexact=login) | Q(email__iexact=login)
        ).distinct()

        if matches.count() != 1:
            raise AuthenticationFailed(self.error_messages["invalid_credentials"])

        candidate = matches.first()
        user = authenticate(
            request=self.context.get("request"),
            username=candidate.get_username(),
            password=attrs["password"],
        )
        if user is None or not user.is_active:
            raise AuthenticationFailed(self.error_messages["invalid_credentials"])

        attrs["user"] = user
        return attrs


class LoginUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "roles"]

    def get_full_name(self, obj) -> str:
        return " ".join(filter(None, [obj.first_name, obj.last_name]))

    def get_roles(self, obj) -> list[str]:
        return list(obj.roles.order_by("code").values_list("code", flat=True))


class LoginResponseSerializer(serializers.Serializer):
    user = LoginUserSerializer()


class CurrentUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "is_active",
            "roles",
            "permissions",
            "profile",
        ]

    def get_full_name(self, obj) -> str:
        return " ".join(filter(None, [obj.first_name, obj.last_name]))

    def get_roles(self, obj) -> list[str]:
        return list(obj.roles.order_by("code").values_list("code", flat=True))

    def get_permissions(self, obj) -> list[str]:
        return sorted(obj.get_all_permissions())

    def get_profile(self, obj) -> dict | None:
        try:
            student = obj.student_profile
        except Student.DoesNotExist:
            return None

        return {
            "student_id": student.id_number,
            "group": student.group.name if student.group else None,
        }


class MessageSerializer(serializers.Serializer):
    message = serializers.CharField()
