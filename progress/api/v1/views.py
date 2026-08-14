from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from enrollments.permissions import StudentCoursePermission
from progress.api.v1.serializers import (
    CourseProgressSerializer,
    LessonProgressSerializer,
    StudentProgressSerializer,
)
from progress.services import CourseProgressService, LessonProgressService


class StudentLessonStartView(APIView):
    permission_classes = (StudentCoursePermission,)

    @extend_schema(
        request=None,
        responses={200: LessonProgressSerializer, 201: LessonProgressSerializer},
    )
    def post(self, request, pk):
        progress, created = LessonProgressService.start_lesson(
            student=request.user,
            lesson_id=pk,
        )
        return Response(
            LessonProgressSerializer(progress).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class StudentLessonCompleteView(APIView):
    permission_classes = (StudentCoursePermission,)

    @extend_schema(
        request=None,
        responses={200: LessonProgressSerializer, 201: LessonProgressSerializer},
    )
    def post(self, request, pk):
        progress, created = LessonProgressService.complete_lesson(
            student=request.user,
            lesson_id=pk,
        )
        return Response(
            LessonProgressSerializer(progress).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class StudentProgressView(APIView):
    permission_classes = (StudentCoursePermission,)

    @extend_schema(responses={200: StudentProgressSerializer})
    def get(self, request):
        summary = CourseProgressService.student_summary(student=request.user)
        return Response(StudentProgressSerializer(summary).data)


class StudentCourseProgressView(APIView):
    permission_classes = (StudentCoursePermission,)

    @extend_schema(responses={200: CourseProgressSerializer})
    def get(self, request, pk):
        summary = CourseProgressService.course_summary(
            student=request.user,
            course_id=pk,
        )
        return Response(CourseProgressSerializer(summary).data)
