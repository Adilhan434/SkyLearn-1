from django.db import transaction
from django.db.models import Max
from rest_framework import serializers

from courses.models import Course
from learning.models import CourseModule, CourseTopic, Lesson


class StructureLessonSerializer(serializers.ModelSerializer):
    lesson_type = serializers.CharField(read_only=True)
    release_type = serializers.CharField(read_only=True)
    required_lesson = serializers.IntegerField(
        source="required_lesson_id",
        allow_null=True,
        read_only=True,
    )

    class Meta:
        model = Lesson
        fields = (
            "id",
            "title",
            "order",
            "lesson_type",
            "estimated_duration_minutes",
            "release_type",
            "release_at",
            "required_lesson",
            "is_published",
        )


class StructureTopicSerializer(serializers.ModelSerializer):
    lessons = StructureLessonSerializer(many=True, read_only=True)

    class Meta:
        model = CourseTopic
        fields = ("id", "title", "order", "lessons")


class StructureModuleSerializer(serializers.ModelSerializer):
    release_type = serializers.CharField(read_only=True)
    topics = StructureTopicSerializer(many=True, read_only=True)

    class Meta:
        model = CourseModule
        fields = (
            "id",
            "title",
            "order",
            "release_type",
            "release_at",
            "topics",
        )


class CourseStructureSerializer(serializers.ModelSerializer):
    course_id = serializers.IntegerField(source="id", read_only=True)
    modules = StructureModuleSerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = ("course_id", "modules")


class CourseModuleWriteSerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(required=False, min_value=1)
    release_type = serializers.CharField(required=False)

    class Meta:
        model = CourseModule
        fields = (
            "id",
            "title",
            "description",
            "order",
            "release_type",
            "release_at",
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

    def validate_release_type(self, value):
        allowed_values = {
            choice_value for choice_value, _label in CourseModule._meta.get_field(
                "release_type"
            ).choices
        }
        if value not in allowed_values:
            raise serializers.ValidationError("Invalid module release type.")
        return value

    def validate(self, attrs):
        instance = self.instance
        release_type = attrs.get(
            "release_type",
            getattr(instance, "release_type", "always"),
        )
        release_at = attrs.get(
            "release_at",
            getattr(instance, "release_at", None),
        )
        if release_type == "date" and release_at is None:
            raise serializers.ValidationError(
                {"release_at": "A date-based module requires release_at."}
            )
        if release_type != "date" and release_at is not None:
            raise serializers.ValidationError(
                {"release_at": "release_at is allowed only for date release."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        course = Course.objects.select_for_update().get(
            pk=self.context["course"].pk
        )
        actor = self.context["request"].user
        if "order" not in validated_data:
            maximum_order = course.modules.aggregate(maximum=Max("order"))[
                "maximum"
            ]
            validated_data["order"] = (maximum_order or 0) + 1
        self._validate_unique_order(course, validated_data["order"])
        return CourseModule.objects.create(
            course=course,
            created_by=actor,
            updated_by=actor,
            **validated_data,
        )

    def update(self, instance, validated_data):
        actor = self.context["request"].user
        order = validated_data.get("order", instance.order)
        self._validate_unique_order(instance.course, order, instance.pk)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.updated_by = actor
        instance.save()
        return instance

    @staticmethod
    def _validate_unique_order(course, order, instance_pk=None):
        modules = course.modules.filter(order=order)
        if instance_pk is not None:
            modules = modules.exclude(pk=instance_pk)
        if modules.exists():
            raise serializers.ValidationError(
                {"order": "A module with this order already exists."}
            )


class DeleteConfirmationSerializer(serializers.Serializer):
    confirm = serializers.BooleanField(default=False, required=False)


class CourseTopicWriteSerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(required=False, min_value=1)

    class Meta:
        model = CourseTopic
        fields = (
            "id",
            "title",
            "description",
            "order",
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

    @transaction.atomic
    def create(self, validated_data):
        module = CourseModule.objects.select_for_update().get(
            pk=self.context["module"].pk
        )
        actor = self.context["request"].user
        if "order" not in validated_data:
            maximum_order = module.topics.aggregate(maximum=Max("order"))[
                "maximum"
            ]
            validated_data["order"] = (maximum_order or 0) + 1
        self._validate_unique_order(module, validated_data["order"])
        return CourseTopic.objects.create(
            module=module,
            created_by=actor,
            updated_by=actor,
            **validated_data,
        )

    def update(self, instance, validated_data):
        actor = self.context["request"].user
        order = validated_data.get("order", instance.order)
        self._validate_unique_order(instance.module, order, instance.pk)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.updated_by = actor
        instance.save()
        return instance

    @staticmethod
    def _validate_unique_order(module, order, instance_pk=None):
        topics = module.topics.filter(order=order)
        if instance_pk is not None:
            topics = topics.exclude(pk=instance_pk)
        if topics.exists():
            raise serializers.ValidationError(
                {"order": "A topic with this order already exists."}
            )
