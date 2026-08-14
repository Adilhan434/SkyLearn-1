import mimetypes
from pathlib import Path

from django.db import transaction
from django.db.models import Max
from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from courses.models import Course
from learning.models import (
    CourseModule,
    CourseTopic,
    LearningMaterial,
    LearningMaterialType,
    Lesson,
    LessonType,
    ReleaseType,
)
from learning.reordering import InvalidStructureOrder


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


class LessonWriteSerializer(serializers.ModelSerializer):
    topic = serializers.PrimaryKeyRelatedField(read_only=True)
    order = serializers.IntegerField(required=False, min_value=1)
    lesson_type = serializers.CharField(required=False)
    release_type = serializers.CharField(required=False)
    required_lesson = serializers.PrimaryKeyRelatedField(
        queryset=Lesson.objects.select_related(
            "topic",
            "topic__module",
            "topic__module__course",
        ),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Lesson
        fields = (
            "id",
            "topic",
            "title",
            "description",
            "lesson_type",
            "content",
            "estimated_duration_minutes",
            "order",
            "release_type",
            "release_at",
            "required_lesson",
            "is_published",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "topic",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )

    def validate_lesson_type(self, value):
        if value not in {choice for choice, _label in LessonType.choices}:
            raise serializers.ValidationError("Invalid lesson type.")
        return value

    def validate_release_type(self, value):
        if value not in {choice for choice, _label in ReleaseType.choices}:
            raise serializers.ValidationError("Invalid lesson release type.")
        return value

    def validate(self, attrs):
        instance = self.instance
        topic = self.context.get("topic") or instance.topic
        release_type = attrs.get(
            "release_type",
            getattr(instance, "release_type", ReleaseType.ALWAYS),
        )
        release_at = attrs.get(
            "release_at",
            getattr(instance, "release_at", None),
        )
        required_lesson = attrs.get(
            "required_lesson",
            getattr(instance, "required_lesson", None),
        )
        errors = {}

        if release_type == ReleaseType.DATE:
            if release_at is None:
                errors["release_at"] = "A date-based lesson requires release_at."
            if required_lesson is not None:
                errors["required_lesson"] = (
                    "A date-based lesson cannot require another lesson."
                )
        elif release_type == ReleaseType.AFTER_LESSON:
            if required_lesson is None:
                errors["required_lesson"] = (
                    "An after-lesson release requires required_lesson."
                )
            if release_at is not None:
                errors["release_at"] = (
                    "An after-lesson release cannot define release_at."
                )
        elif release_at is not None or required_lesson is not None:
            errors["release_type"] = (
                "Release fields do not match the selected release type."
            )

        if required_lesson is not None:
            self._validate_required_lesson(
                instance,
                topic,
                required_lesson,
                errors,
            )
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    @staticmethod
    def _validate_required_lesson(instance, topic, required_lesson, errors):
        if instance is not None and required_lesson.pk == instance.pk:
            errors["required_lesson"] = "A lesson cannot require itself."
            return
        if required_lesson.topic.module.course_id != topic.module.course_id:
            errors["required_lesson"] = (
                "The required lesson must belong to the same course."
            )
            return

        visited = set()
        current = required_lesson
        while current is not None:
            if instance is not None and current.pk == instance.pk:
                errors["required_lesson"] = (
                    "The required lesson would create a dependency cycle."
                )
                return
            if current.pk in visited:
                errors["required_lesson"] = (
                    "The required lesson chain already contains a cycle."
                )
                return
            visited.add(current.pk)
            current = current.required_lesson

    @transaction.atomic
    def create(self, validated_data):
        topic = CourseTopic.objects.select_for_update().get(
            pk=self.context["topic"].pk
        )
        actor = self.context["request"].user
        if "order" not in validated_data:
            maximum_order = topic.lessons.aggregate(maximum=Max("order"))[
                "maximum"
            ]
            validated_data["order"] = (maximum_order or 0) + 1
        self._validate_unique_order(topic, validated_data["order"])
        return Lesson.objects.create(
            topic=topic,
            created_by=actor,
            updated_by=actor,
            **validated_data,
        )

    @transaction.atomic
    def update(self, instance, validated_data):
        actor = self.context["request"].user
        order = validated_data.get("order", instance.order)
        self._validate_unique_order(instance.topic, order, instance.pk)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.updated_by = actor
        instance.save()
        return instance

    @staticmethod
    def _validate_unique_order(topic, order, instance_pk=None):
        lessons = topic.lessons.filter(order=order)
        if instance_pk is not None:
            lessons = lessons.exclude(pk=instance_pk)
        if lessons.exists():
            raise serializers.ValidationError(
                {"order": "A lesson with this order already exists."}
            )


class StructureReorderItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(min_value=1)
    order = serializers.IntegerField(min_value=1)


class StructureReorderSerializer(serializers.Serializer):
    type = serializers.CharField()
    items = StructureReorderItemSerializer(many=True)

    def validate_type(self, value):
        if value not in {"module", "topic", "lesson"}:
            raise InvalidStructureOrder(
                "Type must be module, topic or lesson."
            )
        return value

    def validate_items(self, items):
        if not items:
            raise InvalidStructureOrder("At least one item is required.")
        item_ids = [item["id"] for item in items]
        orders = [item["order"] for item in items]
        if len(item_ids) != len(set(item_ids)):
            raise InvalidStructureOrder("Item IDs must be unique.")
        if len(orders) != len(set(orders)):
            raise InvalidStructureOrder("Order values must be unique.")
        if set(orders) != set(range(1, len(items) + 1)):
            raise InvalidStructureOrder(
                "Order values must form a continuous sequence from 1."
            )
        return items


class LearningMaterialSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, required=False)
    download_allowed = serializers.BooleanField(required=False, default=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = LearningMaterial
        fields = (
            "id",
            "lesson",
            "course",
            "title",
            "description",
            "type",
            "file",
            "external_url",
            "original_filename",
            "mime_type",
            "size",
            "extension",
            "download_allowed",
            "download_url",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "lesson",
            "course",
            "original_filename",
            "mime_type",
            "size",
            "extension",
            "download_url",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )

    @extend_schema_field(OpenApiTypes.URI)
    def get_download_url(self, obj):
        if not obj.file or not obj.download_allowed:
            return None
        return reverse(
            "api-v1:learning-v1:material-download",
            kwargs={"pk": obj.pk},
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        material_type = attrs.get(
            "type",
            instance.type if instance is not None else None,
        )
        is_link = material_type in {
            LearningMaterialType.EXTERNAL_LINK,
            LearningMaterialType.LIBRARY_LINK,
        }
        external_url = attrs.get(
            "external_url",
            instance.external_url if instance is not None else "",
        )
        uploaded_file = attrs.get(
            "file",
            instance.file if instance is not None else None,
        )

        if is_link:
            if not external_url:
                raise serializers.ValidationError(
                    {"external_url": "A link material requires external_url."}
                )
            if "file" in attrs:
                raise serializers.ValidationError(
                    {"file": "A link material cannot contain a file."}
                )
        else:
            if not uploaded_file:
                raise serializers.ValidationError(
                    {"file": "A file material requires a file."}
                )
            if attrs.get("external_url"):
                raise serializers.ValidationError(
                    {"external_url": "A file material cannot contain a URL."}
                )
        return attrs

    @staticmethod
    def _set_file_metadata(validated_data, uploaded_file):
        original_name = Path(uploaded_file.name).name
        guessed_type, _encoding = mimetypes.guess_type(original_name)
        validated_data.update(
            original_filename=original_name,
            mime_type=getattr(uploaded_file, "content_type", "")
            or guessed_type
            or "application/octet-stream",
            size=uploaded_file.size,
            extension=Path(original_name).suffix.lower().lstrip("."),
            external_url="",
        )

    def create(self, validated_data):
        uploaded_file = validated_data.get("file")
        if uploaded_file is not None:
            self._set_file_metadata(validated_data, uploaded_file)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        uploaded_file = validated_data.get("file")
        material_type = validated_data.get("type", instance.type)
        if uploaded_file is not None:
            self._set_file_metadata(validated_data, uploaded_file)
        elif material_type in {
            LearningMaterialType.EXTERNAL_LINK,
            LearningMaterialType.LIBRARY_LINK,
        }:
            validated_data.update(
                file="",
                original_filename="",
                mime_type="",
                size=None,
                extension="",
            )
        return super().update(instance, validated_data)


class CourseMaterialFilterSerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True)
    type = serializers.ChoiceField(
        choices=LearningMaterialType.choices,
        required=False,
    )
    lesson = serializers.IntegerField(required=False, min_value=1)
    module = serializers.IntegerField(required=False, min_value=1)
