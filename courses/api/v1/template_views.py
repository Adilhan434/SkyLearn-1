from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response

from accounts.models import LMSPermissionCode
from courses.copying import course_copy_queryset
from courses.models import CourseTemplate
from courses.permissions import (
    CourseTemplatePermission,
    courses_accessible_to,
)
from courses.templates import (
    create_course_from_template,
    create_course_template,
)

from .serializers import (
    CourseCopySerializer,
    CourseDetailSerializer,
    CourseTemplateSerializer,
)


def active_template_queryset():
    return CourseTemplate.objects.filter(is_active=True).select_related(
        "created_by",
        "updated_by",
    )


class CourseTemplateListCreateView(generics.ListCreateAPIView):
    serializer_class = CourseTemplateSerializer
    permission_classes = (CourseTemplatePermission,)

    def get_queryset(self):
        return active_template_queryset()

    def create(self, request, *args, **kwargs):
        del args, kwargs
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        source_id = values.pop("source_course")
        values.setdefault("description", "")
        values.setdefault("is_active", True)
        source = get_object_or_404(
            courses_accessible_to(request.user, course_copy_queryset()),
            pk=source_id,
        )
        template = create_course_template(
            source=source,
            actor=request.user,
            **values,
        )
        return Response(
            self.get_serializer(template).data,
            status=status.HTTP_201_CREATED,
        )


class CourseTemplateDetailView(generics.RetrieveAPIView):
    serializer_class = CourseTemplateSerializer
    permission_classes = (CourseTemplatePermission,)

    def get_queryset(self):
        return active_template_queryset()


class CourseTemplateCreateCourseView(generics.GenericAPIView):
    serializer_class = CourseCopySerializer
    permission_classes = (CourseTemplatePermission,)
    required_permissions = (
        LMSPermissionCode.COURSES_COPY,
        LMSPermissionCode.COURSES_CREATE,
    )

    def get_queryset(self):
        return active_template_queryset()

    @extend_schema(
        request=CourseCopySerializer,
        responses={201: CourseDetailSerializer},
    )
    def post(self, request, *args, **kwargs):
        del args, kwargs
        template = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course = create_course_from_template(
            template=template,
            actor=request.user,
            **serializer.validated_data,
        )
        return Response(
            CourseDetailSerializer(course).data,
            status=status.HTTP_201_CREATED,
        )
