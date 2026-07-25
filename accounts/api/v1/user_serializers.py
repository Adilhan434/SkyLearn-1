from uuid import uuid4

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from accounts.models import Role, User


class UserReadSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    roles = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field="code",
    )

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
        ]

    def get_email(self, obj) -> str | None:
        return obj.email or None

    def get_full_name(self, obj) -> str:
        return " ".join(filter(None, [obj.first_name, obj.last_name]))


class UserCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        validators=[validate_password],
    )
    roles = serializers.SlugRelatedField(
        many=True,
        slug_field="code",
        queryset=Role.objects.all(),
        allow_empty=False,
    )

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "password",
            "roles",
        ]

    def validate_email(self, value):
        normalized = value.strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )
        return normalized

    def _build_username(self, email):
        if (
            len(email) <= User._meta.get_field("username").max_length
            and not User.objects.filter(username__iexact=email).exists()
        ):
            return email
        return f"user_{uuid4().hex}"

    @transaction.atomic
    def create(self, validated_data):
        roles = validated_data.pop("roles")
        password = validated_data.pop("password")
        user = User(
            username=self._build_username(validated_data["email"]),
            **validated_data,
        )
        user.set_password(password)
        user.save()
        user.roles.set(roles)
        return user

    def to_representation(self, instance):
        return UserReadSerializer(instance, context=self.context).data
