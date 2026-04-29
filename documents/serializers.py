from rest_framework import serializers
from .models import DocumentRequest


class DocumentRequestSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    document_type_display = serializers.CharField(source="get_document_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentRequest
        fields = [
            "id", "student", "student_name", "document_type", "document_type_display",
            "description", "status", "status_display", "methodologist_note",
            "approved_file", "reviewed_by", "reviewed_by_name",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "student", "status", "methodologist_note", "approved_file", "reviewed_by", "created_at", "updated_at"]

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name()
        return None


class DocumentRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentRequest
        fields = ["document_type", "description"]


class DocumentRequestReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentRequest
        fields = ["status", "methodologist_note", "approved_file"]
