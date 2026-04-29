from rest_framework import serializers
from .models import Course, CourseAllocation, Program, AcademicYear, Semester, Module, Notification

class CourseSerializer(serializers.ModelSerializer):
    admin = serializers.PrimaryKeyRelatedField(read_only=True)
    allocated_teachers = serializers.SerializerMethodField()

    def get_allocated_teachers(self, obj):
        allocs = obj.course_allocations.select_related('lecturer').all()
        seen = set()
        result = []
        for a in allocs:
            if a.lecturer_id not in seen:
                seen.add(a.lecturer_id)
                result.append({
                    'id': a.lecturer_id,
                    'name': a.lecturer.get_full_name() or a.lecturer.username,
                })
        return result

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
    lecturer_name = serializers.SerializerMethodField()
    group_name = serializers.CharField(source='group.name', read_only=True)
    semester_name = serializers.CharField(source='semester.name', read_only=True)
    courses_details = serializers.SerializerMethodField()

    def get_lecturer_name(self, obj):
        return obj.lecturer.get_full_name() or obj.lecturer.username

    def get_courses_details(self, obj):
        return [{'id': c.id, 'name': c.name, 'description': c.description} for c in obj.courses.all()]

    class Meta:
        model = CourseAllocation
        fields = '__all__'

class NotificationSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.get_full_name", read_only=True)
    
    class Meta:
        model = Notification
        fields = '__all__'
