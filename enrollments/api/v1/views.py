from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response

from courses.models import Course
from courses.permissions import courses_accessible_to
from enrollments.models import Enrollment, EnrollmentSource
from enrollments.permissions import EnrollmentPermission
from enrollments.services import enroll_student

from .pagination import EnrollmentPagination
from .serializers import EnrollmentSerializer, EnrollmentWriteSerializer


class CourseEnrollmentListCreateView(generics.ListCreateAPIView):
    serializer_class = EnrollmentSerializer
    permission_classes = (EnrollmentPermission,)
    pagination_class = EnrollmentPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return EnrollmentWriteSerializer
        return EnrollmentSerializer

    def get_course(self):
        if not hasattr(self, "course"):
            self.course = get_object_or_404(
                courses_accessible_to(self.request.user, Course.objects.all()),
                pk=self.kwargs["course_pk"],
            )
        return self.course

    def get_queryset(self):
        return (
            Enrollment.objects.filter(course=self.get_course())
            .select_related(
                "student",
                "student__student_profile",
                "course",
                "created_by",
                "updated_by",
            )
            .order_by("-enrolled_at", "-id")
        )

    @extend_schema(
        request=EnrollmentWriteSerializer,
        responses={
            200: EnrollmentSerializer,
            201: EnrollmentSerializer,
        },
    )
    def create(self, request, *args, **kwargs):
        del args, kwargs
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        enrollment, created = enroll_student(
            course=self.get_course(),
            student=values["student"],
            source=values.get("source", EnrollmentSource.MANUAL),
            external_sis_id=values.get("external_sis_id", ""),
            actor=request.user,
        )
        return Response(
            EnrollmentSerializer(
                enrollment,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
