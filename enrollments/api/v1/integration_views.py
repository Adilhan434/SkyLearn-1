from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response

from enrollments.api.v1.integration_serializers import (
    SISSyncRequestSerializer,
    SISSyncResponseSerializer,
)
from enrollments.permissions import EnrollmentPermission
from enrollments.sis import SISIntegrationService


class SISEnrollmentSyncView(generics.GenericAPIView):
    serializer_class = SISSyncRequestSerializer
    permission_classes = (EnrollmentPermission,)

    @extend_schema(
        request=SISSyncRequestSerializer,
        responses={
            200: SISSyncResponseSerializer,
            201: SISSyncResponseSerializer,
        },
    )
    def post(self, request, *args, **kwargs):
        del args, kwargs
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event, processed = SISIntegrationService.sync_enrollment(
            actor=request.user,
            **serializer.validated_data,
        )
        output = SISSyncResponseSerializer(
            event,
            context={"idempotent_replay": not processed},
        )
        return Response(
            output.data,
            status=status.HTTP_201_CREATED if processed else status.HTTP_200_OK,
        )
