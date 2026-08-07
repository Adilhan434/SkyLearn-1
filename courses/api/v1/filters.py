from django_filters import rest_framework as filters

from courses.models import Course


class CourseFilter(filters.FilterSet):
    status = filters.CharFilter(field_name="status")
    semester = filters.NumberFilter(field_name="semester_id")
    faculty = filters.NumberFilter(field_name="faculty_id")

    class Meta:
        model = Course
        fields = ("status", "semester", "faculty")
