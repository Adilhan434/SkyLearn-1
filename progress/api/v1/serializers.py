from rest_framework import serializers

from progress.models import LessonProgress


class LessonProgressSerializer(serializers.ModelSerializer):
    lesson_id = serializers.IntegerField(read_only=True)
    course_id = serializers.IntegerField(source="lesson.course.id", read_only=True)

    class Meta:
        model = LessonProgress
        fields = (
            "id",
            "course_id",
            "lesson_id",
            "status",
            "started_at",
            "completed_at",
            "updated_at",
        )


class CourseProgressSerializer(serializers.Serializer):
    course_id = serializers.IntegerField()
    total_lessons = serializers.IntegerField(min_value=0)
    completed_lessons = serializers.IntegerField(min_value=0)
    progress_percent = serializers.IntegerField(min_value=0, max_value=100)


class StudentProgressSerializer(serializers.Serializer):
    total_courses = serializers.IntegerField(min_value=0)
    total_lessons = serializers.IntegerField(min_value=0)
    completed_lessons = serializers.IntegerField(min_value=0)
    progress_percent = serializers.IntegerField(min_value=0, max_value=100)
    courses = CourseProgressSerializer(many=True)


class DashboardCourseSerializer(CourseProgressSerializer):
    title = serializers.CharField()
    code = serializers.CharField()


class ContinueLearningSerializer(serializers.Serializer):
    course_id = serializers.IntegerField(required=False)
    course_title = serializers.CharField(required=False)
    lesson_id = serializers.IntegerField(required=False)
    lesson_title = serializers.CharField(required=False)
    status = serializers.CharField(required=False)


class DashboardCalendarEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    course_id = serializers.IntegerField()
    title = serializers.CharField()
    event_type = serializers.CharField()
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField(allow_null=True)


class StudentDashboardSerializer(serializers.Serializer):
    active_courses = serializers.IntegerField(min_value=0)
    completed_lessons = serializers.IntegerField(min_value=0)
    overall_progress = serializers.IntegerField(min_value=0, max_value=100)
    continue_learning = ContinueLearningSerializer()
    courses = DashboardCourseSerializer(many=True)
    upcoming_events = DashboardCalendarEventSerializer(many=True)
