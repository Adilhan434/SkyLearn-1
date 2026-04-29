from django.db import models


DOCUMENT_TYPES = [
    ("certificate", "Certificate of Enrollment"),
    ("transcript", "Academic Transcript"),
    ("reference", "Reference Letter"),
    ("military", "Military Reference"),
    ("other", "Other"),
]

STATUS_CHOICES = [
    ("pending", "Pending Review"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]


class DocumentRequest(models.Model):
    student = models.ForeignKey(
        "accounts.Student",
        on_delete=models.CASCADE,
        related_name="document_requests",
    )
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    methodologist_note = models.TextField(blank=True, default="")
    approved_file = models.FileField(upload_to="documents/approved/", null=True, blank=True)
    reviewed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Document Request"
        verbose_name_plural = "Document Requests"

    def __str__(self):
        return f"{self.get_document_type_display()} — {self.student}"
