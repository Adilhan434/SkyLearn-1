from rest_framework import serializers

from organization.models import Department, Faculty, Program, Semester
from organization.models import Department, Faculty, Group, Program, Semester


class FacultySerializer(serializers.ModelSerializer):
    class Meta:
        model = Faculty
        fields = ("id", "name", "code", "is_active")


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("id", "faculty", "name", "code", "is_active")


class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = (
            "id",
            "department",
            "name",
            "code",
            "degree_level",
            "is_active",
        )


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = (
            "id",
            "program",
            "name",
            "admission_year",
            "is_active",
        )


class SemesterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Semester
        fields = ("id", "name", "start_date", "end_date", "is_active")
