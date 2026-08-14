from django.db import transaction
from django.db.models import Max
from rest_framework import serializers

from courses.models import Course
from learning.models import (
    CourseModule,
    CourseTopic,
    Lesson,
    LessonType,
    ReleaseType,
)


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
