from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.models import RoleCode, User
from audit.models import (
    CourseHistoryAction,
    CourseHistoryEvent,
    CourseHistoryObjectType,
)
from audit.services import record_course_history_event
from courses.copying import CourseCodeExists
from courses.models import (
    Course,
    CourseTeachingAssignment,
    CourseTeachingRole,
    CourseTemplate,
)
from organization.models import Department, Faculty, Program, Semester
from organization.models import Department, Faculty, Group, Program, Semester


class SemesterSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Semester
        fields = ("id", "name")


class FacultySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Faculty
        fields = ("id", "name", "code")


class DepartmentSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("id", "name", "code")


class ProgramSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = ("id", "name", "code")


class GroupSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ("id", "name", "admission_year")


class TeacherSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "full_name")

    def get_full_name(self, obj) -> str:
        return obj.get_full_name().strip()


class PrimaryTeacherMixin:
    @extend_schema_field(TeacherSummarySerializer(allow_null=True))
    def get_teacher(self, obj):
        assignments = getattr(obj, "primary_teacher_assignments", None)
        if assignments is None:
            assignment = (
                obj.teaching_assignments.filter(
                    role=CourseTeachingRole.TEACHER,
                    is_primary=True,
                )
                .select_related("user")
                .first()
            )
        else:
            assignment = assignments[0] if assignments else None
        if assignment is None:
            return None
        return TeacherSummarySerializer(assignment.user).data


class CourseListSerializer(PrimaryTeacherMixin, serializers.ModelSerializer):
    teacher = serializers.SerializerMethodField()
    semester = SemesterSummarySerializer(read_only=True)
    faculty = FacultySummarySerializer(read_only=True)
    department = DepartmentSummarySerializer(read_only=True)
    program = ProgramSummarySerializer(read_only=True)
    group = GroupSummarySerializer(read_only=True)

    class Meta:
        model = Course
        fields = (
            "id",
            "title",
            "code",
            "status",
            "language",
            "credits",
            "semester",
            "teacher",
            "faculty",
            "department",
            "program",
            "group",
            "cover",
            "start_date",
            "end_date",
            "updated_at",
        )


class CourseDetailSerializer(PrimaryTeacherMixin, serializers.ModelSerializer):
    teacher = serializers.SerializerMethodField()
    semester = SemesterSummarySerializer(read_only=True)
    faculty = FacultySummarySerializer(read_only=True)
    department = DepartmentSummarySerializer(read_only=True)
    program = ProgramSummarySerializer(read_only=True)
    group = GroupSummarySerializer(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    updated_by = serializers.PrimaryKeyRelatedField(read_only=True)
    published_by = serializers.PrimaryKeyRelatedField(read_only=True)

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
            "group",
            "status",
            "start_date",
            "end_date",
            "cover",
            "syllabus",
            "review_comment",
            "published_at",
            "published_by",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )


class ReturnForRevisionSerializer(serializers.Serializer):
    comment = serializers.CharField(allow_blank=False, trim_whitespace=True)


class ReadinessCheckSerializer(serializers.Serializer):
    key = serializers.CharField()
    status = serializers.CharField()
    message = serializers.CharField(required=False)


class CourseReadinessSerializer(serializers.Serializer):
    score = serializers.IntegerField(min_value=0, max_value=100)
    ready_for_review = serializers.BooleanField()
    checks = ReadinessCheckSerializer(many=True)


class CourseHistoryActorSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "full_name")

    def get_full_name(self, obj) -> str:
        return " ".join(
            part for part in (obj.first_name, obj.last_name) if part
        )


class CourseHistoryObjectSerializer(serializers.Serializer):
    type = serializers.CharField()
    id = serializers.IntegerField()
    title = serializers.CharField()


class CourseHistoryEventSerializer(serializers.ModelSerializer):
    actor = CourseHistoryActorSerializer(read_only=True, allow_null=True)
    object = serializers.SerializerMethodField()

    class Meta:
        model = CourseHistoryEvent
        fields = ("id", "action", "actor", "object", "created_at")

    @extend_schema_field(CourseHistoryObjectSerializer)
    def get_object(self, obj):
        return {
            "type": obj.object_type,
            "id": obj.object_id,
            "title": obj.object_title,
        }


class CourseCopySerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, allow_blank=False)
    code = serializers.CharField(max_length=50, allow_blank=False)

    def validate_code(self, value):
        normalized_code = value.strip().upper()
        if Course.objects.filter(code__iexact=normalized_code).exists():
            raise CourseCodeExists()
        return normalized_code


class CourseTemplateSerializer(serializers.ModelSerializer):
    source_course = serializers.IntegerField(
        write_only=True,
        min_value=1,
        required=True,
    )
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    updated_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = CourseTemplate
        fields = (
            "id",
            "title",
            "description",
            "is_active",
            "source_course",
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


class CourseWriteSerializer(serializers.ModelSerializer):
    teacher = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        write_only=True,
    )

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
            "group",
            "status",
            "start_date",
            "end_date",
            "cover",
            "syllabus",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )

    def validate_code(self, value):
        normalized_code = value.strip().upper()
        courses = Course.objects.filter(code__iexact=normalized_code)
        if self.instance is not None:
            courses = courses.exclude(pk=self.instance.pk)
        if courses.exists():
            raise serializers.ValidationError(
                "A course with this code already exists."
            )
        return normalized_code

    def validate_teacher(self, teacher):
        if not teacher.is_active:
            raise serializers.ValidationError("Teacher must be active.")
        if not teacher.roles.filter(code=RoleCode.TEACHER).exists():
            raise serializers.ValidationError(
                "Selected user must have the teacher role."
            )
        return teacher

    def validate(self, attrs):
        instance = self.instance
        start_date = attrs.get(
            "start_date",
            getattr(instance, "start_date", None),
        )
        end_date = attrs.get(
            "end_date",
            getattr(instance, "end_date", None),
        )
        faculty = attrs.get("faculty", getattr(instance, "faculty", None))
        department = attrs.get(
            "department",
            getattr(instance, "department", None),
        )
        program = attrs.get("program", getattr(instance, "program", None))
        group = attrs.get("group", getattr(instance, "group", None))
        errors = {}

        for field_name, organization_object in (
            ("faculty", faculty),
            ("department", department),
            ("program", program),
            ("group", group),
        ):
            if organization_object and not organization_object.is_active:
                errors[field_name] = "Selected object must be active."
        if start_date and end_date and end_date < start_date:
            errors["end_date"] = "End date must be on or after start date."
        if faculty and department and department.faculty_id != faculty.id:
            errors["department"] = (
                "Department must belong to the selected faculty."
            )
        if department and program and program.department_id != department.id:
            errors["program"] = (
                "Program must belong to the selected department."
            )
        if program and group and group.program_id != program.id:
            errors["group"] = (
                "Group must belong to the selected program."
            )
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        teacher = validated_data.pop("teacher", None)
        course = Course.objects.create(
            created_by=user,
            updated_by=user,
            **validated_data,
        )
        if teacher is None and user.roles.filter(code=RoleCode.TEACHER).exists():
            teacher = user
        if teacher is not None:
            self._set_primary_teacher(course, teacher, user)
        record_course_history_event(
            course=course,
            action=CourseHistoryAction.COURSE_CREATED,
            actor=user,
            object_type=CourseHistoryObjectType.COURSE,
            object_id=course.pk,
            object_title=course.title,
        )
        return course

    @transaction.atomic
    def update(self, instance, validated_data):
        user = self.context["request"].user
        changed_fields = set(validated_data)
        teacher = validated_data.pop("teacher", None)
        if not changed_fields:
            return instance
        instance.updated_by = user
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if teacher is not None:
            self._set_primary_teacher(instance, teacher, user)
        record_course_history_event(
            course=instance,
            action=CourseHistoryAction.COURSE_UPDATED,
            actor=user,
            object_type=CourseHistoryObjectType.COURSE,
            object_id=instance.pk,
            object_title=instance.title,
            details={"changed_fields": sorted(changed_fields)},
        )
        return instance

    @staticmethod
    def _set_primary_teacher(course, teacher, actor):
        CourseTeachingAssignment.objects.filter(
            course=course,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        ).exclude(user=teacher).update(
            is_primary=False,
            updated_by=actor,
        )
        assignment, created = CourseTeachingAssignment.objects.get_or_create(
            course=course,
            user=teacher,
            defaults={
                "role": CourseTeachingRole.TEACHER,
                "is_primary": True,
                "created_by": actor,
                "updated_by": actor,
            },
        )
        if not created:
            assignment.role = CourseTeachingRole.TEACHER
            assignment.is_primary = True
            assignment.updated_by = actor
            assignment.save(
                update_fields=("role", "is_primary", "updated_by", "updated_at")
            )
