from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import DocumentRequest
from .serializers import DocumentRequestSerializer, DocumentRequestCreateSerializer, DocumentRequestReviewSerializer
from .permissions import IsMethodologist, IsStudent


class StudentDocumentListCreateView(generics.ListCreateAPIView):
    """Student: list own requests and create new ones."""
    permission_classes = [IsStudent]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return DocumentRequestCreateSerializer
        return DocumentRequestSerializer

    def get_queryset(self):
        return DocumentRequest.objects.filter(student=self.request.user.student_profile)

    def perform_create(self, serializer):
        serializer.save(student=self.request.user.student_profile)


class StudentDocumentDetailView(generics.RetrieveAPIView):
    """Student: view single request detail."""
    permission_classes = [IsStudent]
    serializer_class = DocumentRequestSerializer

    def get_queryset(self):
        return DocumentRequest.objects.filter(student=self.request.user.student_profile)


class MethodologistDocumentListView(generics.ListAPIView):
    """Methodologist: see all document requests."""
    permission_classes = [IsMethodologist]
    serializer_class = DocumentRequestSerializer

    def get_queryset(self):
        qs = DocumentRequest.objects.all()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class MethodologistDocumentReviewView(APIView):
    """Methodologist: approve or reject a document request."""
    permission_classes = [IsMethodologist]

    def patch(self, request, pk):
        try:
            doc = DocumentRequest.objects.get(pk=pk)
        except DocumentRequest.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        serializer = DocumentRequestReviewSerializer(doc, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(reviewed_by=request.user)

        return Response(DocumentRequestSerializer(doc).data)
