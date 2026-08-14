from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from audit.models import CourseHistoryAction, CourseHistoryObjectType
from audit.services import record_course_history_event
from courses.models import Course
from learning.file_validation import validate_material_file
from learning.models import (
    CourseModule,
    CourseTopic,
    LearningMaterial,
    LearningMaterialType,
    Lesson,
    LessonType,
    ReleaseType,
    ScormPackage,
    ScormPackageStatus,
    VideoProcessingStatus,
)
from learning.reordering import InvalidStructureOrder
from learning.scorm import validate_scorm_package
from learning.video_processing import VideoProcessingService


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
            choice_value
            for choice_value, _label in CourseModule._meta.get_field(
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
        course = Course.objects.select_for_update().get(pk=self.context["course"].pk)
        actor = self.context["request"].user
        if "order" not in validated_data:
            maximum_order = course.modules.aggregate(maximum=Max("order"))["maximum"]
            validated_data["order"] = (maximum_order or 0) + 1
        self._validate_unique_order(course, validated_data["order"])
        module = CourseModule.objects.create(
            course=course,
            created_by=actor,
            updated_by=actor,
            **validated_data,
        )
        record_course_history_event(
            course=course,
            action=CourseHistoryAction.MODULE_CREATED,
            actor=actor,
            object_type=CourseHistoryObjectType.MODULE,
            object_id=module.pk,
            object_title=module.title,
        )
        return module

    @transaction.atomic
    def update(self, instance, validated_data):
        actor = self.context["request"].user
        changed_fields = set(validated_data)
        if not changed_fields:
            return instance
        order = validated_data.get("order", instance.order)
        self._validate_unique_order(instance.course, order, instance.pk)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.updated_by = actor
        instance.save()
        record_course_history_event(
            course=instance.course,
            action=CourseHistoryAction.MODULE_UPDATED,
            actor=actor,
            object_type=CourseHistoryObjectType.MODULE,
            object_id=instance.pk,
            object_title=instance.title,
            details={"changed_fields": sorted(changed_fields)},
        )
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
            maximum_order = module.topics.aggregate(maximum=Max("order"))["maximum"]
            validated_data["order"] = (maximum_order or 0) + 1
        self._validate_unique_order(module, validated_data["order"])
        topic = CourseTopic.objects.create(
            module=module,
            created_by=actor,
            updated_by=actor,
            **validated_data,
        )
        record_course_history_event(
            course=module.course,
            action=CourseHistoryAction.TOPIC_CREATED,
            actor=actor,
            object_type=CourseHistoryObjectType.TOPIC,
            object_id=topic.pk,
            object_title=topic.title,
        )
        return topic

    @transaction.atomic
    def update(self, instance, validated_data):
        actor = self.context["request"].user
        changed_fields = set(validated_data)
        if not changed_fields:
            return instance
        order = validated_data.get("order", instance.order)
        self._validate_unique_order(instance.module, order, instance.pk)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.updated_by = actor
        instance.save()
        record_course_history_event(
            course=instance.module.course,
            action=CourseHistoryAction.TOPIC_UPDATED,
            actor=actor,
            object_type=CourseHistoryObjectType.TOPIC,
            object_id=instance.pk,
            object_title=instance.title,
            details={"changed_fields": sorted(changed_fields)},
        )
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
                errors[
                    "required_lesson"
                ] = "A date-based lesson cannot require another lesson."
        elif release_type == ReleaseType.AFTER_LESSON:
            if required_lesson is None:
                errors[
                    "required_lesson"
                ] = "An after-lesson release requires required_lesson."
            if release_at is not None:
                errors[
                    "release_at"
                ] = "An after-lesson release cannot define release_at."
        elif release_at is not None or required_lesson is not None:
            errors[
                "release_type"
            ] = "Release fields do not match the selected release type."

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
            errors[
                "required_lesson"
            ] = "The required lesson must belong to the same course."
            return

        visited = set()
        current = required_lesson
        while current is not None:
            if instance is not None and current.pk == instance.pk:
                errors[
                    "required_lesson"
                ] = "The required lesson would create a dependency cycle."
                return
            if current.pk in visited:
                errors[
                    "required_lesson"
                ] = "The required lesson chain already contains a cycle."
                return
            visited.add(current.pk)
            current = current.required_lesson

    @transaction.atomic
    def create(self, validated_data):
        topic = CourseTopic.objects.select_for_update().get(pk=self.context["topic"].pk)
        actor = self.context["request"].user
        if "order" not in validated_data:
            maximum_order = topic.lessons.aggregate(maximum=Max("order"))["maximum"]
            validated_data["order"] = (maximum_order or 0) + 1
        self._validate_unique_order(topic, validated_data["order"])
        lesson = Lesson.objects.create(
            topic=topic,
            created_by=actor,
            updated_by=actor,
            **validated_data,
        )
        record_course_history_event(
            course=topic.module.course,
            action=CourseHistoryAction.LESSON_CREATED,
            actor=actor,
            object_type=CourseHistoryObjectType.LESSON,
            object_id=lesson.pk,
            object_title=lesson.title,
        )
        return lesson

    @transaction.atomic
    def update(self, instance, validated_data):
        actor = self.context["request"].user
        changed_fields = set(validated_data)
        if not changed_fields:
            return instance
        order = validated_data.get("order", instance.order)
        self._validate_unique_order(instance.topic, order, instance.pk)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.updated_by = actor
        instance.save()
        record_course_history_event(
            course=instance.topic.module.course,
            action=CourseHistoryAction.LESSON_UPDATED,
            actor=actor,
            object_type=CourseHistoryObjectType.LESSON,
            object_id=instance.pk,
            object_title=instance.title,
            details={"changed_fields": sorted(changed_fields)},
        )
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
            raise InvalidStructureOrder("Type must be module, topic or lesson.")
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
    playback_url = serializers.SerializerMethodField()

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
            "video_status",
            "duration_seconds",
            "playback_url",
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
            "video_status",
            "duration_seconds",
            "playback_url",
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

    @extend_schema_field(OpenApiTypes.URI)
    def get_playback_url(self, obj):
        if (
            obj.type != LearningMaterialType.VIDEO
            or not obj.file
            or obj.video_status != VideoProcessingStatus.READY
        ):
            return None
        return reverse(
            "api-v1:learning-v1:material-playback",
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
            if (
                instance is not None
                and material_type != instance.type
                and "file" not in attrs
            ):
                raise serializers.ValidationError(
                    {"file": "Changing the material type requires a new file."}
                )
            if "file" in attrs:
                try:
                    metadata = validate_material_file(
                        attrs["file"],
                        material_type,
                    )
                except ValidationError as exc:
                    raise serializers.ValidationError(exc.message_dict) from exc
                attrs.update(metadata.as_model_fields())
        return attrs

    def create(self, validated_data):
        if validated_data.get("file") is not None:
            validated_data["external_url"] = ""
        is_video = validated_data.get("type") == LearningMaterialType.VIDEO
        if is_video:
            validated_data["video_status"] = VideoProcessingStatus.UPLOADED
        material = super().create(validated_data)
        if is_video:
            VideoProcessingService().process(material)
        return material

    def update(self, instance, validated_data):
        uploaded_file = validated_data.get("file")
        material_type = validated_data.get("type", instance.type)
        if uploaded_file is not None:
            validated_data["external_url"] = ""
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
        should_process_video = material_type == LearningMaterialType.VIDEO and (
            uploaded_file is not None or instance.type != material_type
        )
        if should_process_video:
            validated_data["video_status"] = VideoProcessingStatus.UPLOADED
            validated_data["duration_seconds"] = None
        elif material_type != LearningMaterialType.VIDEO:
            validated_data["video_status"] = ""
            validated_data["duration_seconds"] = None
        material = super().update(instance, validated_data)
        if should_process_video:
            VideoProcessingService().process(material)
        return material


class CourseMaterialFilterSerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True)
    type = serializers.ChoiceField(
        choices=LearningMaterialType.choices,
        required=False,
    )
    lesson = serializers.IntegerField(required=False, min_value=1)
    module = serializers.IntegerField(required=False, min_value=1)


class ScormPackageSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)
    launch_url = serializers.SerializerMethodField()

    class Meta:
        model = ScormPackage
        fields = (
            "id",
            "course",
            "lesson",
            "file",
            "title",
            "version",
            "launch_path",
            "status",
            "launch_url",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "course",
            "lesson",
            "version",
            "launch_path",
            "status",
            "launch_url",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )

    @extend_schema_field(OpenApiTypes.URI)
    def get_launch_url(self, obj):
        if obj.status != ScormPackageStatus.READY or not obj.launch_path:
            return None
        return reverse(
            "api-v1:learning-v1:scorm-content",
            kwargs={"pk": obj.pk, "path": obj.launch_path},
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        try:
            metadata = validate_scorm_package(attrs["file"])
        except ValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        attrs.update(
            version=metadata.version,
            launch_path=metadata.launch_path,
            status=ScormPackageStatus.READY,
        )
        return attrs
