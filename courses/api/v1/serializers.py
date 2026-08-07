from rest_framework import serializers

from courses.models import Course


class CourseListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ("id", "title", "code", "status", "credits")


class CourseDetailSerializer(serializers.ModelSerializer):
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
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        faculty = attrs.get("faculty")
        department = attrs.get("department")
        program = attrs.get("program")
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

    def create(self, validated_data):
        user = self.context["request"].user
        return Course.objects.create(
            created_by=user,
            updated_by=user,
            **validated_data,
        )
