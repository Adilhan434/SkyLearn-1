from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.models import RoleCode, User
from courses.models import Course, CourseTeachingAssignment, CourseTeachingRole
from organization.models import Department, Faculty, Program, Semester


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
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    updated_by = serializers.PrimaryKeyRelatedField(read_only=True)

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
            "start_date",
            "end_date",
            "cover",
            "syllabus",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )


class CourseWriteSerializer(serializers.ModelSerializer):
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
            "faculty",
            "department",
            "program",
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
        errors = {}

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
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        course = Course.objects.create(
            created_by=user,
            updated_by=user,
            **validated_data,
        )
        if user.roles.filter(code=RoleCode.TEACHER).exists():
            CourseTeachingAssignment.objects.create(
                course=course,
                user=user,
                role=CourseTeachingRole.TEACHER,
                is_primary=True,
                created_by=user,
                updated_by=user,
            )
        return course

    def update(self, instance, validated_data):
        instance.updated_by = self.context["request"].user
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
