from django.db.models import Q
from django_filters import rest_framework as filters
from rest_framework.filters import SearchFilter

from courses.models import (
    Course,
    CourseLanguage,
    CourseStatus,
    CourseTeachingRole,
)


class CourseFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=CourseStatus.choices)
    semester = filters.NumberFilter(field_name="semester_id")
    faculty = filters.NumberFilter(field_name="faculty_id")
    department = filters.NumberFilter(field_name="department_id")
    program = filters.NumberFilter(field_name="program_id")
    group = filters.NumberFilter(field_name="group_id")
    teacher = filters.NumberFilter(method="filter_teacher")
    language = filters.ChoiceFilter(choices=CourseLanguage.choices)
    created_by = filters.NumberFilter(field_name="created_by_id")

    class Meta:
        model = Course
        fields = (
            "status",
            "semester",
            "faculty",
            "department",
            "program",
            "group",
            "teacher",
            "language",
            "created_by",
        )

    @staticmethod
    def filter_teacher(queryset, name, value):
        del name
        return queryset.filter(
            teaching_assignments__user_id=value,
            teaching_assignments__role=CourseTeachingRole.TEACHER,
        ).distinct()


class CourseSearchFilter(SearchFilter):
    """Search course metadata and names of assigned teachers."""

    def filter_queryset(self, request, queryset, view):
        del view
        search_terms = self.get_search_terms(request)
        for term in search_terms:
            teacher_match = Q(
                teaching_assignments__role=CourseTeachingRole.TEACHER
            ) & (
                Q(teaching_assignments__user__first_name__icontains=term)
                | Q(teaching_assignments__user__last_name__icontains=term)
            )
            queryset = queryset.filter(
                Q(title__icontains=term)
                | Q(code__icontains=term)
                | Q(description__icontains=term)
                | teacher_match
            )
        return queryset.distinct()
