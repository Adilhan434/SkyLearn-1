from datetime import date
from io import BytesIO
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode
from config.storage_backends import PrivateFileSystemStorage
from courses.models import Course, CourseTeachingAssignment, CourseTeachingRole
from learning.models import (
    CourseModule,
    CourseTopic,
    Lesson,
    ScormPackage,
    ScormPackageStatus,
)
from organization.models import DegreeLevel, Department, Faculty, Program, Semester


MANIFEST = b"""<?xml version="1.0" encoding="UTF-8"?>
<manifest xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
          xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">
  <metadata><schemaversion>1.2</schemaversion></metadata>
  <organizations />
  <resources>
    <resource identifier="resource-1" type="webcontent"
              adlcp:scormtype="sco" href="index.html" />
  </resources>
</manifest>
"""
LAUNCH_HTML = b"<html><body><script src='scripts/app.js'></script></body></html>"


def scorm_zip(files=None):
    content = BytesIO()
    package_files = {
        "imsmanifest.xml": MANIFEST,
        "index.html": LAUNCH_HTML,
        "scripts/app.js": b"window.scormReady = true;",
    }
    if files is not None:
        package_files = files
    with ZipFile(content, "w") as archive:
        for name, body in package_files.items():
            archive.writestr(name, body)
    return content.getvalue()


class ScormPackageAPITests(APITestCase):
    def setUp(self):
        self.private_directory = TemporaryDirectory()
        file_field = ScormPackage._meta.get_field("file")
        original_storage = file_field.storage
        file_field.storage = PrivateFileSystemStorage(
            location=self.private_directory.name
        )
        self.addCleanup(setattr, file_field, "storage", original_storage)
        self.addCleanup(self.private_directory.cleanup)

        user_model = get_user_model()
        self.manager = user_model.objects.create_user(username="scorm-manager")
        self.manager.roles.add(Role.objects.get(code=RoleCode.CONTENT_MANAGER))
        self.teacher = user_model.objects.create_user(username="scorm-teacher")
        self.teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        faculty = Faculty.objects.create(name="SCORM Faculty", code="SCORM-FAC")
        department = Department.objects.create(
            faculty=faculty,
            name="SCORM Department",
            code="SCORM-DEP",
        )
        program = Program.objects.create(
            department=department,
            name="SCORM Program",
            code="SCORM-PROG",
            degree_level=DegreeLevel.BACHELOR,
        )
        semester = Semester.objects.create(
            name="SCORM Semester",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        self.course = Course.objects.create(
            title="SCORM Course",
            code="SCORM-101",
            credits=5,
            semester=semester,
            faculty=faculty,
            department=department,
            program=program,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
            created_by=self.manager,
            updated_by=self.manager,
        )
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=self.teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        )
        module = CourseModule.objects.create(
            course=self.course,
            title="SCORM Module",
            order=1,
        )
        topic = CourseTopic.objects.create(
            module=module,
            title="SCORM Topic",
            order=1,
        )
        self.lesson = Lesson.objects.create(
            topic=topic,
            title="SCORM Lesson",
            order=1,
        )

    def collection_url(self):
        return reverse(
            "api-v1:learning-v1:lesson-scorm-list-create",
            kwargs={"lesson_pk": self.lesson.pk},
        )

    @staticmethod
    def detail_url(package):
        return reverse(
            "api-v1:learning-v1:scorm-detail",
            kwargs={"pk": package.pk},
        )

    @staticmethod
    def content_url(package, path=None):
        return reverse(
            "api-v1:learning-v1:scorm-content",
            kwargs={"pk": package.pk, "path": path or package.launch_path},
        )

    def upload(self, content=None, filename="course.zip"):
        return self.client.post(
            self.collection_url(),
            {
                "title": "SCORM introduction",
                "file": SimpleUploadedFile(
                    filename,
                    scorm_zip() if content is None else content,
                    content_type="application/zip",
                ),
            },
            format="multipart",
        )

    def test_manager_uploads_valid_package_and_gets_launch_url(self):
        self.client.force_authenticate(self.manager)

        response = self.upload()
        package = ScormPackage.objects.get(pk=response.data["id"])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["version"], "1.2")
        self.assertEqual(response.data["launch_path"], "index.html")
        self.assertEqual(response.data["status"], ScormPackageStatus.READY)
        self.assertEqual(response.data["launch_url"], self.content_url(package))
        self.assertEqual(package.course, self.course)
        self.assertEqual(package.lesson, self.lesson)

        detail_response = self.client.get(self.detail_url(package))
        list_response = self.client.get(self.collection_url())

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["id"], package.pk)
        self.assertEqual(
            [item["id"] for item in list_response.data],
            [package.pk],
        )
        with self.assertRaisesMessage(ValueError, "protected API"):
            package.file.url

    def test_launch_and_relative_asset_are_served_with_security_headers(self):
        self.client.force_authenticate(self.manager)
        package = ScormPackage.objects.get(pk=self.upload().data["id"])

        launch_response = self.client.get(self.content_url(package))
        asset_response = self.client.get(self.content_url(package, "scripts/app.js"))

        launch_content = b"".join(launch_response.streaming_content)
        asset_content = b"".join(asset_response.streaming_content)

        self.assertEqual(launch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(launch_content, LAUNCH_HTML)
        self.assertEqual(launch_response["Content-Type"], "text/html")
        self.assertIn("sandbox", launch_response["Content-Security-Policy"])
        self.assertIn(
            "http://localhost:5173", launch_response["Content-Security-Policy"]
        )
        self.assertNotIn("X-Frame-Options", launch_response)
        self.assertEqual(asset_response.status_code, status.HTTP_200_OK)
        self.assertEqual(asset_response["Content-Type"], "application/javascript")
        self.assertEqual(asset_content, b"window.scormReady = true;")

    def test_upload_requires_authentication(self):
        response = self.upload()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unassigned_teacher_cannot_retrieve_package(self):
        self.client.force_authenticate(self.manager)
        package = ScormPackage.objects.get(pk=self.upload().data["id"])
        outsider = get_user_model().objects.create_user(username="scorm-outsider")
        outsider.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.client.force_authenticate(outsider)

        response = self.client.get(self.detail_url(package))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_package_without_manifest_is_rejected(self):
        self.client.force_authenticate(self.manager)

        response = self.upload(scorm_zip({"index.html": LAUNCH_HTML}))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("imsmanifest.xml", str(response.data))
        self.assertFalse(ScormPackage.objects.exists())

    def test_non_zip_extension_is_rejected(self):
        self.client.force_authenticate(self.manager)

        response = self.upload(filename="course.bin")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ZIP file", str(response.data))

    def test_package_with_missing_launch_file_is_rejected(self):
        self.client.force_authenticate(self.manager)

        response = self.upload(scorm_zip({"imsmanifest.xml": MANIFEST}))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("launch resource", str(response.data))

    def test_invalid_zip_and_unsafe_member_are_rejected(self):
        self.client.force_authenticate(self.manager)
        responses = (
            self.upload(b"not-a-zip"),
            self.upload(
                scorm_zip(
                    {
                        "imsmanifest.xml": MANIFEST,
                        "index.html": LAUNCH_HTML,
                        "../escape.js": b"unsafe",
                    }
                )
            ),
        )

        for response in responses:
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_package_asset_returns_stable_error(self):
        self.client.force_authenticate(self.manager)
        package = ScormPackage.objects.get(pk=self.upload().data["id"])

        response = self.client.get(self.content_url(package, "missing.js"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"]["code"],
            "scorm_content_unavailable",
        )
