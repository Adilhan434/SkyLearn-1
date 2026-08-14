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
