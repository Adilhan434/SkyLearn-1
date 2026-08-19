from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from organization.models import Department, Faculty, Program, Semester

from .serializers import (
    DepartmentSerializer,
    FacultySerializer,
    ProgramSerializer,
    SemesterSerializer,
)


class ActiveOrganizationListView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)


class FacultyListView(ActiveOrganizationListView):
    queryset = Faculty.objects.filter(is_active=True)
    serializer_class = FacultySerializer


class DepartmentListView(ActiveOrganizationListView):
    queryset = Department.objects.filter(
        is_active=True,
        faculty__is_active=True,
    )
    serializer_class = DepartmentSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_fields = ("faculty",)


class ProgramListView(ActiveOrganizationListView):
    queryset = Program.objects.filter(
        is_active=True,
        department__is_active=True,
        department__faculty__is_active=True,
    )
    serializer_class = ProgramSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_fields = ("department",)


class SemesterListView(ActiveOrganizationListView):
    queryset = Semester.objects.filter(is_active=True)
    serializer_class = SemesterSerializer
