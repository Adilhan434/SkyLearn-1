from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from .models import Course, CourseAllocation, Program, AcademicYear, Semester, Module, Notification
from .serializers import (
    CourseSerializer, CourseAllocationSerializer, ProgramSerializer,
    AcademicYearSerializer, SemesterSerializer, ModuleSerializer, NotificationSerializer
)
from .permissions import IsAdminOrMethodologist, IsAdminOrAccountant

# Semester Views
class SemesterListAPIView(generics.ListAPIView):
    queryset = Semester.objects.all()
    serializer_class = SemesterSerializer

class SemesterCreateAPIView(generics.CreateAPIView):
    queryset = Semester.objects.all()
    serializer_class = SemesterSerializer
    permission_classes = [IsAdminUser]

class SemesterUpdateAPIView(generics.UpdateAPIView):
    queryset = Semester.objects.all()
    serializer_class = SemesterSerializer
    permission_classes = [IsAdminUser]

class SemesterRetrieveDestroyAPIView(generics.RetrieveDestroyAPIView):
    queryset = Semester.objects.all()
    serializer_class = SemesterSerializer

# Program Views
class ProgramListAPIView(generics.ListAPIView):
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer
    permission_classes = [IsAuthenticated]

class ProgramCreateAPIView(generics.CreateAPIView):
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer
    permission_classes = [IsAdminOrMethodologist]

class ProgramUpdateAPIView(generics.UpdateAPIView):
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer
    permission_classes = [IsAdminOrMethodologist]

class ProgramRetrieveDestroyAPIView(generics.RetrieveDestroyAPIView):
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer
    permission_classes = [IsAdminOrMethodologist]

# Academic Year Views
class AcademicYearListAPIView(generics.ListAPIView):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer

class AcademicYearCreateAPIView(generics.CreateAPIView):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer
    permission_classes = [IsAdminUser]

class AcademicYearUpdateAPIView(generics.UpdateAPIView):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer
    permission_classes = [IsAdminUser]

class AcademicYearRetrieveDestroyAPIView(generics.RetrieveDestroyAPIView):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer

# Module Views
class ModuleListAPIView(generics.ListAPIView):
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer

class ModuleCreateAPIView(generics.CreateAPIView):
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer
    permission_classes = [IsAdminUser]

class ModuleUpdateAPIView(generics.UpdateAPIView):
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer
    permission_classes = [IsAdminUser]

class ModuleRetrieveDestroyAPIView(generics.RetrieveDestroyAPIView):
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer

# Course Views
class CourseListAPIView(generics.ListAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

class CourseCreateAPIView(generics.CreateAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAdminOrMethodologist]

    def perform_create(self, serializer):
        if self.request.user.is_superuser:
            serializer.save(admin=self.request.user)
        else:
            serializer.save()

class CourseRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAdminOrMethodologist]

# Course Allocation Views
class CourseAllocationListAPIView(generics.ListAPIView):
    queryset = CourseAllocation.objects.all()
    serializer_class = CourseAllocationSerializer

class CourseAllocationCreateAPIView(generics.CreateAPIView):
    queryset = CourseAllocation.objects.all()
    serializer_class = CourseAllocationSerializer
    permission_classes = [IsAdminOrMethodologist]

class CourseAllocationRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CourseAllocation.objects.all()
    serializer_class = CourseAllocationSerializer
    permission_classes = [IsAdminOrMethodologist]

class TeacherCourseAllocations(generics.ListAPIView):
    serializer_class = CourseAllocationSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return CourseAllocation.objects.filter(lecturer=self.request.user)

class CourseAllocationListByGroupAPIView(generics.ListAPIView):
    serializer_class = CourseAllocationSerializer
    def get_queryset(self):
        group_id = self.kwargs.get('group_id')
        return CourseAllocation.objects.filter(group_id=group_id)

# Notification Views
class NotificationListAPIView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

class NotificationMarkReadAPIView(generics.UpdateAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)
    def perform_update(self, serializer):
        serializer.save(is_read=True)
