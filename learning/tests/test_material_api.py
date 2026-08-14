from datetime import date
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode
from config.storage_backends import PrivateFileSystemStorage
from courses.models import (
    Course,
    CourseTeachingAssignment,
    CourseTeachingRole,
)
from learning.models import (
    CourseModule,
    CourseTopic,
    LearningMaterial,
    LearningMaterialType,
    Lesson,
)
from organization.models import DegreeLevel, Department, Faculty, Program, Semester


PDF_CONTENT = b"%PDF-1.4\nprotected content\n%%EOF"


class LearningMaterialAPITests(APITestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        material_file_field = LearningMaterial._meta.get_field("file")
        original_storage = material_file_field.storage
        material_file_field.storage = PrivateFileSystemStorage(
            location=self.media_directory.name
        )
        self.addCleanup(
            setattr,
            material_file_field,
            "storage",
            original_storage,
        )
        self.media_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_directory.cleanup)

        user_model = get_user_model()
        self.manager = user_model.objects.create_user(username="material-manager")
        self.manager.roles.add(Role.objects.get(code=RoleCode.CONTENT_MANAGER))
        self.teacher = user_model.objects.create_user(username="material-teacher")
        self.teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        faculty = Faculty.objects.create(name="Engineering", code="MAT-API-FAC")
        department = Department.objects.create(
            faculty=faculty,
            name="Computer Science",
            code="MAT-API-DEP",
        )
        program = Program.objects.create(
            department=department,
            name="Software Engineering",
            code="MAT-API-PROG",
            degree_level=DegreeLevel.BACHELOR,
        )
        semester = Semester.objects.create(
            name="Material API Semester",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        self.course = Course.objects.create(
            title="Material API Course",
            code="MAT-API-101",
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
        self.module = CourseModule.objects.create(
            course=self.course,
            title="Materials Module",
            order=1,
        )
        self.topic = CourseTopic.objects.create(
            module=self.module,
            title="Materials Topic",
            order=1,
        )
        self.lesson = Lesson.objects.create(
            topic=self.topic,
            title="Materials Lesson",
            order=1,
        )

    def lesson_material_url(self, lesson=None):
        return reverse(
            "api-v1:learning-v1:lesson-material-list-create",
            kwargs={"lesson_pk": (lesson or self.lesson).pk},
        )

    def course_material_url(self):
        return reverse(
            "api-v1:courses-v1:material-list",
            kwargs={"pk": self.course.pk},
        )

    @staticmethod
    def detail_url(material):
        return reverse(
            "api-v1:learning-v1:material-detail",
            kwargs={"pk": material.pk},
        )

    @staticmethod
    def download_url(material):
        return reverse(
            "api-v1:learning-v1:material-download",
            kwargs={"pk": material.pk},
        )

    def create_file_material(self, **overrides):
        values = {
            "lesson": self.lesson,
            "course": self.course,
            "title": "Handbook",
            "type": LearningMaterialType.PDF,
            "file": "learning/materials/handbook.pdf",
            "original_filename": "handbook.pdf",
            "mime_type": "application/pdf",
            "size": 8,
            "extension": "pdf",
            "created_by": self.manager,
            "updated_by": self.manager,
        }
        values.update(overrides)
        return LearningMaterial.objects.create(**values)

    def test_material_list_requires_authentication(self):
        response = self.client.get(self.lesson_material_url())

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_manager_uploads_file_and_metadata_is_derived(self):
        self.client.force_authenticate(self.manager)
        uploaded_file = SimpleUploadedFile(
            "guide.pdf",
            PDF_CONTENT,
            content_type="application/pdf",
        )

        response = self.client.post(
            self.lesson_material_url(),
            {
                "title": "Programming guide",
                "description": "Student guide",
                "type": LearningMaterialType.PDF,
                "file": uploaded_file,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        material = LearningMaterial.objects.get(pk=response.data["id"])
        self.assertEqual(material.course, self.course)
        self.assertEqual(material.lesson, self.lesson)
        self.assertEqual(material.original_filename, "guide.pdf")
        self.assertEqual(material.mime_type, "application/pdf")
        self.assertEqual(material.size, len(PDF_CONTENT))
        self.assertEqual(material.extension, "pdf")
        self.assertEqual(material.created_by, self.manager)
        self.assertNotIn("file", response.data)
        self.assertEqual(response.data["download_url"], self.download_url(material))

    def test_manager_creates_external_link(self):
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.lesson_material_url(),
            {
                "title": "External library",
                "type": LearningMaterialType.LIBRARY_LINK,
                "external_url": "https://library.example/resource",
                "download_allowed": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["external_url"],
            "https://library.example/resource",
        )
        self.assertIsNone(response.data["download_url"])

    def test_material_source_is_required_and_must_match_type(self):
        self.client.force_authenticate(self.manager)

        missing_file = self.client.post(
            self.lesson_material_url(),
            {"title": "No file", "type": LearningMaterialType.PDF},
            format="json",
        )
        missing_url = self.client.post(
            self.lesson_material_url(),
            {
                "title": "No URL",
                "type": LearningMaterialType.EXTERNAL_LINK,
            },
            format="json",
        )

        self.assertEqual(missing_file.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(missing_url.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", missing_file.data["error"]["fields"])
        self.assertIn("external_url", missing_url.data["error"]["fields"])

    def test_upload_rejects_spoofed_file_content(self):
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.lesson_material_url(),
            {
                "title": "Spoofed PDF",
                "type": LearningMaterialType.PDF,
                "file": SimpleUploadedFile(
                    "spoofed.pdf",
                    b"not really a PDF",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", response.data["error"]["fields"])
        self.assertFalse(LearningMaterial.objects.exists())

    def test_changing_file_material_type_requires_new_file(self):
        material = self.create_file_material()
        self.client.force_authenticate(self.manager)

        response = self.client.patch(
            self.detail_url(material),
            {"type": LearningMaterialType.VIDEO},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", response.data["error"]["fields"])
        material.refresh_from_db()
        self.assertEqual(material.type, LearningMaterialType.PDF)

    def test_lesson_list_returns_only_its_materials(self):
        expected = self.create_file_material()
        second_lesson = Lesson.objects.create(
            topic=self.topic,
            title="Second lesson",
            order=2,
        )
        self.create_file_material(
            lesson=second_lesson,
            title="Other material",
        )
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.lesson_material_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [expected.pk])

    def test_assigned_teacher_can_retrieve_and_patch_material(self):
        material = self.create_file_material()
        self.client.force_authenticate(self.teacher)

        detail_response = self.client.get(self.detail_url(material))
        patch_response = self.client.patch(
            self.detail_url(material),
            {"title": "Teacher handbook"},
            format="json",
        )

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        material.refresh_from_db()
        self.assertEqual(material.title, "Teacher handbook")
        self.assertEqual(material.updated_by, self.teacher)

    def test_manager_can_delete_material(self):
        material = self.create_file_material()
        self.client.force_authenticate(self.manager)

        response = self.client.delete(self.detail_url(material))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(LearningMaterial.objects.filter(pk=material.pk).exists())

    def test_unassigned_teacher_cannot_access_material_by_id(self):
        material = self.create_file_material()
        teacher = get_user_model().objects.create_user(
            username="unassigned-material-teacher"
        )
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.client.force_authenticate(teacher)

        response = self.client.get(self.detail_url(material))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_archived_course_material_cannot_be_changed(self):
        material = self.create_file_material()
        self.course.status = "archived"
        self.course.save(update_fields=("status",))
        self.client.force_authenticate(self.manager)

        response = self.client.patch(
            self.detail_url(material),
            {"title": "Forbidden change"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_course_material_list_supports_all_filters(self):
        expected = self.create_file_material(title="Python handbook")
        second_module = CourseModule.objects.create(
            course=self.course,
            title="Second Module",
            order=2,
        )
        second_topic = CourseTopic.objects.create(
            module=second_module,
            title="Second Topic",
            order=1,
        )
        second_lesson = Lesson.objects.create(
            topic=second_topic,
            title="Second Lesson",
            order=1,
        )
        self.create_file_material(
            lesson=second_lesson,
            title="Video introduction",
            type=LearningMaterialType.VIDEO,
            file="learning/materials/video.mp4",
            original_filename="video.mp4",
            mime_type="video/mp4",
            extension="mp4",
        )
        self.client.force_authenticate(self.manager)

        responses = (
            self.client.get(self.course_material_url(), {"search": "handbook"}),
            self.client.get(
                self.course_material_url(),
                {"type": LearningMaterialType.PDF},
            ),
            self.client.get(
                self.course_material_url(),
                {"lesson": self.lesson.pk},
            ),
            self.client.get(
                self.course_material_url(),
                {"module": self.module.pk},
            ),
        )

        for response in responses:
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(
                [item["id"] for item in response.data],
                [expected.pk],
            )

    def test_course_material_list_rejects_invalid_filter(self):
        self.client.force_authenticate(self.manager)

        response = self.client.get(
            self.course_material_url(),
            {"module": "not-an-id"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("module", response.data["error"]["fields"])

    def test_download_returns_protected_file(self):
        self.client.force_authenticate(self.manager)
        upload_response = self.client.post(
            self.lesson_material_url(),
            {
                "title": "Download guide",
                "type": LearningMaterialType.PDF,
                "file": SimpleUploadedFile(
                    "download.pdf",
                    PDF_CONTENT,
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )
        material = LearningMaterial.objects.get(pk=upload_response.data["id"])

        response = self.client.get(self.download_url(material))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = b"".join(response.streaming_content)

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("download.pdf", response["Content-Disposition"])
        self.assertEqual(body, PDF_CONTENT)

    def test_private_material_has_no_direct_storage_url(self):
        self.client.force_authenticate(self.manager)
        upload_response = self.client.post(
            self.lesson_material_url(),
            {
                "title": "Private guide",
                "type": LearningMaterialType.PDF,
                "file": SimpleUploadedFile(
                    "private.pdf",
                    PDF_CONTENT,
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )
        material = LearningMaterial.objects.get(pk=upload_response.data["id"])

        with self.assertRaisesMessage(ValueError, "protected API"):
            material.file.url

    def test_unassigned_teacher_cannot_download_material(self):
        material = self.create_file_material()
        teacher = get_user_model().objects.create_user(
            username="unassigned-download-teacher"
        )
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.client.force_authenticate(teacher)

        response = self.client.get(self.download_url(material))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_requires_authentication(self):
        material = self.create_file_material()

        response = self.client.get(self.download_url(material))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_download_obeys_download_allowed(self):
        material = self.create_file_material(download_allowed=False)
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.download_url(material))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.data["error"]["code"],
            "material_download_not_allowed",
        )

    def test_external_link_cannot_be_downloaded_as_file(self):
        material = LearningMaterial.objects.create(
            lesson=self.lesson,
            course=self.course,
            title="External resource",
            type=LearningMaterialType.EXTERNAL_LINK,
            external_url="https://example.com/resource",
        )
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.download_url(material))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"]["code"],
            "material_file_unavailable",
        )
