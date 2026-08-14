from django.contrib.auth import get_user_model
from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.models import RoleCode
from courses.api.v1.serializers import (
    DepartmentSummarySerializer,
    FacultySummarySerializer,
    PrimaryTeacherMixin,
    ProgramSummarySerializer,
    SemesterSummarySerializer,
)
from courses.models import Course
from enrollments.models import Enrollment
from learning.availability import evaluate_lesson_availability
from learning.models import (
    CourseModule,
    CourseTopic,
    LearningMaterial,
    LearningMaterialType,
    Lesson,
    VideoProcessingStatus,
)
from progress.models import LessonProgressStatus
from progress.services import calculate_course_progress


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


class StudentCourseSerializer(PrimaryTeacherMixin, serializers.ModelSerializer):
    teacher = serializers.SerializerMethodField()
    semester = SemesterSummarySerializer(read_only=True)
    faculty = FacultySummarySerializer(read_only=True)
    department = DepartmentSummarySerializer(read_only=True)
    program = ProgramSummarySerializer(read_only=True)

    class Meta:
        model = Course
        fields = (
            "id",
            "title",
            "code",
            "description",
            "language",
            "credits",
            "semester",
            "teacher",
            "faculty",
            "department",
            "program",
            "status",
            "cover",
            "syllabus",
            "start_date",
            "end_date",
        )


class StudentMaterialSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    playback_url = serializers.SerializerMethodField()

    class Meta:
        model = LearningMaterial
        fields = (
            "id",
            "title",
            "description",
            "type",
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


class StudentLessonSerializer(serializers.ModelSerializer):
    content = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    lock_reason = serializers.SerializerMethodField()
    materials = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = (
            "id",
            "title",
            "description",
            "lesson_type",
            "content",
            "estimated_duration_minutes",
            "order",
            "release_type",
            "release_at",
            "required_lesson",
            "status",
            "is_available",
            "lock_reason",
            "materials",
        )

    @extend_schema_field(serializers.CharField())
    def get_status(self, obj):
        progress = self.context.get("lesson_progress_by_id", {}).get(obj.pk)
        return progress.status if progress else LessonProgressStatus.NOT_STARTED

    def _availability(self, obj):
        if not hasattr(obj, "_student_availability"):
            obj._student_availability = evaluate_lesson_availability(
                obj,
                completed_lesson_ids=self.context.get(
                    "completed_lesson_ids",
                    (),
                ),
            )
        return obj._student_availability

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_content(self, obj):
        return obj.content if self._availability(obj).is_available else None

    @extend_schema_field(serializers.BooleanField())
    def get_is_available(self, obj):
        return self._availability(obj).is_available

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_lock_reason(self, obj):
        return self._availability(obj).lock_reason

    @extend_schema_field(StudentMaterialSerializer(many=True))
    def get_materials(self, obj):
        if not self._availability(obj).is_available:
            return []
        return StudentMaterialSerializer(
            obj.materials.all(),
            many=True,
            context=self.context,
        ).data


class StudentTopicSerializer(serializers.ModelSerializer):
    lessons = StudentLessonSerializer(many=True, read_only=True)

    class Meta:
        model = CourseTopic
        fields = ("id", "title", "description", "order", "lessons")


class StudentModuleSerializer(serializers.ModelSerializer):
    topics = StudentTopicSerializer(many=True, read_only=True)

    class Meta:
        model = CourseModule
        fields = (
            "id",
            "title",
            "description",
            "order",
            "release_type",
            "release_at",
            "topics",
        )


class StudentCourseDetailSerializer(StudentCourseSerializer):
    overall_progress = serializers.SerializerMethodField()
    structure = serializers.SerializerMethodField()

    class Meta(StudentCourseSerializer.Meta):
        fields = StudentCourseSerializer.Meta.fields + (
            "overall_progress",
            "structure",
        )

    @extend_schema_field(serializers.IntegerField(min_value=0, max_value=100))
    def get_overall_progress(self, obj):
        return calculate_course_progress(
            obj,
            self.context.get("completed_lesson_ids", ()),
        )["progress_percent"]

    @extend_schema_field(StudentModuleSerializer(many=True))
    def get_structure(self, obj):
        return StudentModuleSerializer(
            obj.modules.all(),
            many=True,
            context=self.context,
        ).data
