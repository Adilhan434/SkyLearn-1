from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from learning.scorm import validate_scorm_package

from .test_scorm_api import LAUNCH_HTML, MANIFEST, scorm_zip


def uploaded_package(content, name="course.zip"):
    return SimpleUploadedFile(name, content, content_type="application/zip")


class ScormPackageValidationTests(SimpleTestCase):
    def assert_invalid(self, content, message):
        with self.assertRaisesMessage(ValidationError, message):
            validate_scorm_package(uploaded_package(content))

    def test_empty_upload_is_rejected(self):
        self.assert_invalid(b"", "cannot be empty")

    def test_forbidden_or_malformed_manifest_xml_is_rejected(self):
        manifests = (
            (b"<!DOCTYPE manifest><manifest />", "forbidden XML"),
            (b"<manifest>", "XML is invalid"),
            (b"<manifest><resources /></manifest>", "launch resource"),
        )

        for manifest, message in manifests:
            with self.subTest(message=message):
                self.assert_invalid(
                    scorm_zip(
                        {
                            "imsmanifest.xml": manifest,
                            "index.html": LAUNCH_HTML,
                        }
                    ),
                    message,
                )

    @override_settings(SCORM_MAX_FILES=1)
    def test_file_count_limit_is_enforced(self):
        self.assert_invalid(scorm_zip(), "too many files")

    @override_settings(SCORM_MAX_UNCOMPRESSED_SIZE=10)
    def test_uncompressed_size_limit_is_enforced(self):
        self.assert_invalid(scorm_zip(), "too large after decompression")

    def test_unsafe_compression_ratio_is_rejected(self):
        content = BytesIO()
        with ZipFile(content, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("imsmanifest.xml", MANIFEST)
            archive.writestr("index.html", b"A" * 100_000)

        self.assert_invalid(content.getvalue(), "compression ratio is unsafe")

    @override_settings(MATERIAL_MAX_UPLOAD_SIZE=1)
    def test_upload_size_limit_is_enforced(self):
        self.assert_invalid(scorm_zip(), "exceeds the upload limit")
