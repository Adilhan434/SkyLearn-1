from rest_framework import serializers
from .models import Course, CourseAllocation, Program, AcademicYear, Semester, Module, Notification

class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = '__all__'

class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = '__all__'

class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = '__all__'

class SemesterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Semester
        fields = '__all__'

class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = '__all__'

class CourseAllocationSerializer(serializers.ModelSerializer):
    lecturer_name = serializers.CharField(source='lecturer.get_full_name', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)
    semester_name = serializers.CharField(source='semester.name', read_only=True)
    
    class Meta:
        model = CourseAllocation
        fields = '__all__'

class NotificationSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.get_full_name", read_only=True)
    
    class Meta:
        model = Notification
        fields = '__all__'
