from io import BytesIO
from zipfile import ZipFile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from learning.file_validation import validate_material_file
from learning.models import LearningMaterialType


class MaterialFileValidationTests(SimpleTestCase):
    @staticmethod
    def upload(name, content, content_type="application/octet-stream"):
        return SimpleUploadedFile(name, content, content_type=content_type)

    def test_valid_pdf_returns_trusted_metadata(self):
        content = b"%PDF-1.7\ncontent\n%%EOF"
        uploaded_file = self.upload("lecture.pdf", content, "application/pdf")

        metadata = validate_material_file(
            uploaded_file,
            LearningMaterialType.PDF,
        )

        self.assertEqual(metadata.original_filename, "lecture.pdf")
        self.assertEqual(metadata.mime_type, "application/pdf")
        self.assertEqual(metadata.size, len(content))
        self.assertEqual(metadata.extension, "pdf")

    def test_empty_file_is_rejected(self):
        uploaded_file = self.upload("empty.pdf", b"", "application/pdf")

        with self.assertRaisesMessage(ValidationError, "Empty files"):
            validate_material_file(uploaded_file, LearningMaterialType.PDF)

    @override_settings(MATERIAL_MAX_UPLOAD_SIZE=4, MATERIAL_MAX_UPLOAD_SIZE_MB=1)
    def test_oversized_file_is_rejected(self):
        uploaded_file = self.upload(
            "large.pdf",
            b"%PDF-1.7",
            "application/pdf",
        )

        with self.assertRaisesMessage(ValidationError, "maximum upload size"):
            validate_material_file(uploaded_file, LearningMaterialType.PDF)

    def test_executable_extension_is_rejected(self):
        uploaded_file = self.upload("malware.exe", b"MZ executable")

        with self.assertRaisesMessage(ValidationError, "Executable"):
            validate_material_file(uploaded_file, LearningMaterialType.OTHER)

    def test_renamed_executable_content_is_rejected(self):
        uploaded_file = self.upload(
            "notes.txt",
            b"MZ executable content disguised as text",
            "text/plain",
        )

        with self.assertRaisesMessage(ValidationError, "Executable file content"):
            validate_material_file(uploaded_file, LearningMaterialType.OTHER)

    def test_deceptive_double_extension_is_rejected(self):
        uploaded_file = self.upload(
            "lecture.exe.pdf",
            b"%PDF-1.7\ncontent",
            "application/pdf",
        )

        with self.assertRaisesMessage(ValidationError, "Double extensions"):
            validate_material_file(uploaded_file, LearningMaterialType.PDF)

    def test_normal_dotted_filename_is_allowed(self):
        uploaded_file = self.upload(
            "lecture.final.pdf",
            b"%PDF-1.7\ncontent",
            "application/pdf",
        )

        metadata = validate_material_file(
            uploaded_file,
            LearningMaterialType.PDF,
        )

        self.assertEqual(metadata.original_filename, "lecture.final.pdf")

    def test_extension_must_match_material_type(self):
        uploaded_file = self.upload(
            "lecture.pdf",
            b"%PDF-1.7\ncontent",
            "application/pdf",
        )

        with self.assertRaisesMessage(ValidationError, "material type"):
            validate_material_file(uploaded_file, LearningMaterialType.VIDEO)

    def test_spoofed_file_content_is_rejected(self):
        uploaded_file = self.upload(
            "fake.pdf",
            b"This is not a PDF.",
            "application/pdf",
        )

        with self.assertRaisesMessage(ValidationError, "content"):
            validate_material_file(uploaded_file, LearningMaterialType.PDF)

    def test_declared_mime_must_match_detected_content(self):
        uploaded_file = self.upload(
            "lecture.pdf",
            b"%PDF-1.7\ncontent",
            "text/plain",
        )

        with self.assertRaisesMessage(ValidationError, "MIME type"):
            validate_material_file(uploaded_file, LearningMaterialType.PDF)

    def test_valid_docx_must_contain_word_document(self):
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types />")
            archive.writestr("word/document.xml", "<document />")
        uploaded_file = self.upload(
            "document.docx",
            buffer.getvalue(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        metadata = validate_material_file(
            uploaded_file,
            LearningMaterialType.DOCX,
        )

        self.assertEqual(
            metadata.mime_type,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    def test_docx_with_wrong_container_content_is_rejected(self):
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("ppt/presentation.xml", "<presentation />")
        uploaded_file = self.upload(
            "document.docx",
            buffer.getvalue(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        with self.assertRaisesMessage(ValidationError, "does not match"):
            validate_material_file(uploaded_file, LearningMaterialType.DOCX)

    def test_video_signature_is_checked(self):
        uploaded_file = self.upload(
            "lecture.mp4",
            b"\x00\x00\x00\x18ftypmp42video-data",
            "video/mp4",
        )

        metadata = validate_material_file(
            uploaded_file,
            LearningMaterialType.VIDEO,
        )

        self.assertEqual(metadata.mime_type, "video/mp4")
