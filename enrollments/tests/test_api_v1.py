from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode
from courses.models import (
    Course,
    CourseStatus,
    CourseTeachingAssignment,
    CourseTeachingRole,
)
from enrollments.models import Enrollment, EnrollmentSource, EnrollmentStatus
from learning.models import (
    CourseModule,
    CourseTopic,
    LearningMaterial,
    LearningMaterialType,
    Lesson,
    ReleaseType,
)
from organization.models import DegreeLevel, Department, Faculty, Program, Semester
from progress.models import LessonProgress, LessonProgressStatus


class EnrollmentAPITests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(username="enrollment-admin")
        self.admin.roles.add(Role.objects.get(code=RoleCode.LMS_ADMIN))
        self.student = user_model.objects.create_user(username="student-2026")
        self.student.roles.add(Role.objects.get(code=RoleCode.STUDENT))
        self.other_student = user_model.objects.create_user(username="student-2027")
        self.other_student.roles.add(Role.objects.get(code=RoleCode.STUDENT))
        faculty = Faculty.objects.create(name="Engineering", code="ENG")
        department = Department.objects.create(
            faculty=faculty,
            name="Computer Science",
            code="CS",
        )
        program = Program.objects.create(
            department=department,
            name="Software Engineering",
            code="SE",
            degree_level=DegreeLevel.BACHELOR,
        )
        semester = Semester.objects.create(
            name="Fall 2026",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        course_values = {
            "credits": 5,
            "semester": semester,
            "faculty": faculty,
            "department": department,
            "program": program,
            "start_date": date(2026, 9, 1),
            "end_date": date(2026, 12, 20),
            "created_by": self.admin,
            "updated_by": self.admin,
        }
        self.course = Course.objects.create(
            title="Introduction to Programming",
            code="CS101",
            **course_values,
        )
        self.other_course = Course.objects.create(
            title="Databases",
            code="CS202",
            **course_values,
        )

    def url(self, course=None):
        return reverse(
            "api-v1:courses-v1:enrollment-list-create",
            kwargs={"course_pk": (course or self.course).pk},
        )

    def test_admin_creates_manual_active_enrollment(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            self.url(),
            {"student": self.student.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        enrollment = Enrollment.objects.get(pk=response.data["id"])
        self.assertEqual(enrollment.student, self.student)
        self.assertEqual(enrollment.course, self.course)
        self.assertEqual(enrollment.status, EnrollmentStatus.ACTIVE)
        self.assertEqual(enrollment.source, EnrollmentSource.MANUAL)
        self.assertEqual(enrollment.created_by, self.admin)
        self.assertEqual(enrollment.updated_by, self.admin)

    def test_list_is_paginated_and_scoped_to_requested_course(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        Enrollment.objects.create(
            student=self.other_student,
            course=self.other_course,
        )
        self.client.force_authenticate(self.admin)

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data),
            {"count", "next", "previous", "results"},
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["student"], self.student.pk)
        self.assertEqual(response.data["results"][0]["course"], self.course.pk)

    def test_duplicate_active_enrollment_returns_stable_error(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            self.url(),
            {"student": self.student.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "already_enrolled")
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_post_reactivates_existing_non_active_enrollment(self):
        old_enrolled_at = timezone.now() - timedelta(days=30)
        enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            status=EnrollmentStatus.WITHDRAWN,
            source=EnrollmentSource.SIS_SYNC,
            external_sis_id="old-sis-id",
            enrolled_at=old_enrolled_at,
        )
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            self.url(),
            {
                "student": self.student.pk,
                "source": EnrollmentSource.MANUAL,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        enrollment.refresh_from_db()
        self.assertEqual(response.data["id"], enrollment.pk)
        self.assertEqual(enrollment.status, EnrollmentStatus.ACTIVE)
        self.assertEqual(enrollment.source, EnrollmentSource.MANUAL)
        self.assertEqual(enrollment.external_sis_id, "")
        self.assertGreater(enrollment.enrolled_at, old_enrolled_at)
        self.assertEqual(enrollment.updated_by, self.admin)
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_post_rejects_inactive_or_non_student_user(self):
        user_model = get_user_model()
        non_student = user_model.objects.create_user(username="teacher-user")
        inactive_student = user_model.objects.create_user(
            username="inactive-student",
            is_active=False,
        )
        inactive_student.roles.add(Role.objects.get(code=RoleCode.STUDENT))
        self.client.force_authenticate(self.admin)

        non_student_response = self.client.post(
            self.url(),
            {"student": non_student.pk},
            format="json",
        )
        inactive_response = self.client.post(
            self.url(),
            {"student": inactive_student.pk},
            format="json",
        )

        self.assertEqual(
            non_student_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(inactive_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Enrollment.objects.count(), 0)

    def test_student_cannot_list_or_create_enrollments(self):
        self.client.force_authenticate(self.student)

        list_response = self.client.get(self.url())
        create_response = self.client.post(
            self.url(),
            {"student": self.student.pk},
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Enrollment.objects.exists())

    def test_assigned_teacher_can_view_but_cannot_manage_enrollments(self):
        teacher = get_user_model().objects.create_user(username="course-teacher")
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        )
        self.client.force_authenticate(teacher)

        list_response = self.client.get(self.url())
        create_response = self.client.post(
            self.url(),
            {"student": self.student.pk},
            format="json",
        )
        foreign_response = self.client.get(self.url(self.other_course))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(foreign_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_endpoint_requires_authentication(self):
        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_route_has_stable_name(self):
        self.assertEqual(
            self.url(),
            f"/api/v1/courses/{self.course.pk}/enrollments/",
        )


class StudentCourseAPITests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.student = user_model.objects.create_user(
            username="student-courses",
            first_name="Student",
            last_name="Demo",
        )
        self.student.roles.add(Role.objects.get(code=RoleCode.STUDENT))
        self.other_student = user_model.objects.create_user(username="other-student")
        self.other_student.roles.add(Role.objects.get(code=RoleCode.STUDENT))
        self.teacher = user_model.objects.create_user(
            username="student-course-teacher",
            first_name="Teacher",
            last_name="Demo",
        )
        self.teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        faculty = Faculty.objects.create(name="Engineering", code="ENG")
        department = Department.objects.create(
            faculty=faculty,
            name="Computer Science",
            code="CS",
        )
        program = Program.objects.create(
            department=department,
            name="Software Engineering",
            code="SE",
            degree_level=DegreeLevel.BACHELOR,
        )
        semester = Semester.objects.create(
            name="Fall 2026",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        self.course_values = {
            "credits": 5,
            "semester": semester,
            "faculty": faculty,
            "department": department,
            "program": program,
            "start_date": date(2026, 9, 1),
            "end_date": date(2026, 12, 20),
        }
        self.published_course = self.create_course(
            "Published Course",
            "PUB-101",
            CourseStatus.PUBLISHED,
        )
        CourseTeachingAssignment.objects.create(
            course=self.published_course,
            user=self.teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        )
        Enrollment.objects.create(
            student=self.student,
            course=self.published_course,
        )

    def create_course(self, title, code, course_status):
        return Course.objects.create(
            title=title,
            code=code,
            status=course_status,
            **self.course_values,
        )

    def list_url(self):
        return reverse("api-v1:student-v1:course-list")

    def detail_url(self, course):
        return reverse(
            "api-v1:student-v1:course-detail",
            kwargs={"pk": course.pk},
        )

    def lesson_detail_url(self, lesson):
        return reverse(
            "api-v1:student-v1:lesson-detail",
            kwargs={"pk": lesson.pk},
        )

    def build_student_structure(self):
        module = CourseModule.objects.create(
            course=self.published_course,
            title="Foundations",
            description="Module description",
            order=1,
        )
        topic = CourseTopic.objects.create(
            module=module,
            title="Introduction",
            description="Topic description",
            order=1,
        )
        first_lesson = Lesson.objects.create(
            topic=topic,
            title="First lesson",
            content="Visible lesson content",
            order=1,
            is_published=True,
        )
        second_lesson = Lesson.objects.create(
            topic=topic,
            title="Second lesson",
            content="Locked lesson secret",
            order=2,
            release_type=ReleaseType.AFTER_LESSON,
            required_lesson=first_lesson,
            is_published=True,
        )
        Lesson.objects.create(
            topic=topic,
            title="Internal unpublished lesson",
            order=3,
            is_published=False,
        )
        material = LearningMaterial.objects.create(
            lesson=first_lesson,
            course=self.published_course,
            title="Student handbook",
            type=LearningMaterialType.PDF,
            file="learning/materials/student-handbook.pdf",
            original_filename="student-handbook.pdf",
            mime_type="application/pdf",
            size=12,
            extension="pdf",
        )
        locked_material = LearningMaterial.objects.create(
            lesson=second_lesson,
            course=self.published_course,
            title="Locked handbook",
            type=LearningMaterialType.PDF,
            file="learning/materials/locked-handbook.pdf",
            original_filename="locked-handbook.pdf",
            mime_type="application/pdf",
            size=12,
            extension="pdf",
        )
        return first_lesson, second_lesson, material, locked_material

    def test_student_list_contains_only_own_active_published_courses(self):
        withdrawn = self.create_course(
            "Withdrawn Course",
            "WITHDRAWN-1",
            CourseStatus.PUBLISHED,
        )
        draft = self.create_course("Draft Course", "DRAFT-1", CourseStatus.DRAFT)
        archived = self.create_course(
            "Archived Course",
            "ARCHIVED-1",
            CourseStatus.ARCHIVED,
        )
        foreign = self.create_course(
            "Foreign Course",
            "FOREIGN-1",
            CourseStatus.PUBLISHED,
        )
        Enrollment.objects.create(
            student=self.student,
            course=withdrawn,
            status=EnrollmentStatus.WITHDRAWN,
        )
        Enrollment.objects.create(student=self.student, course=draft)
        Enrollment.objects.create(student=self.student, course=archived)
        Enrollment.objects.create(student=self.other_student, course=foreign)
        self.client.force_authenticate(self.student)

        response = self.client.get(self.list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data),
            {"count", "next", "previous", "results"},
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.published_course.pk)

    def test_student_course_response_exposes_safe_metadata(self):
        self.client.force_authenticate(self.student)

        response = self.client.get(self.detail_url(self.published_course))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "PUB-101")
        self.assertEqual(
            response.data["teacher"],
            {"id": self.teacher.pk, "full_name": "Teacher Demo"},
        )
        self.assertNotIn("review_comment", response.data)
        self.assertNotIn("published_by", response.data)
        self.assertNotIn("created_by", response.data)
        self.assertNotIn("updated_by", response.data)

    def test_detail_contains_published_structure_locks_and_materials(self):
        (
            first_lesson,
            second_lesson,
            material,
            _locked_material,
        ) = self.build_student_structure()
        self.client.force_authenticate(self.student)

        response = self.client.get(self.detail_url(self.published_course))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["overall_progress"], 0)
        modules = response.data["structure"]
        self.assertEqual(len(modules), 1)
        lessons = modules[0]["topics"][0]["lessons"]
        self.assertEqual(
            [item["id"] for item in lessons], [first_lesson.pk, second_lesson.pk]
        )
        self.assertEqual(lessons[0]["status"], "not_started")
        self.assertTrue(lessons[0]["is_available"])
        self.assertIsNone(lessons[0]["lock_reason"])
        self.assertFalse(lessons[1]["is_available"])
        self.assertEqual(
            lessons[1]["lock_reason"],
            "Complete the required lesson.",
        )
        self.assertIsNone(lessons[1]["content"])
        self.assertEqual(lessons[1]["materials"], [])
        self.assertEqual(lessons[0]["materials"][0]["id"], material.pk)
        self.assertNotIn("created_by", lessons[0]["materials"][0])
        self.assertEqual(
            lessons[0]["materials"][0]["download_url"],
            reverse(
                "api-v1:learning-v1:material-download",
                kwargs={"pk": material.pk},
            ),
        )

    def test_student_lesson_detail_respects_release_availability(self):
        first_lesson, second_lesson, material, _ = self.build_student_structure()
        self.client.force_authenticate(self.student)

        available = self.client.get(self.lesson_detail_url(first_lesson))
        locked = self.client.get(self.lesson_detail_url(second_lesson))

        self.assertEqual(available.status_code, status.HTTP_200_OK)
        self.assertTrue(available.data["is_available"])
        self.assertEqual(available.data["content"], "Visible lesson content")
        self.assertEqual(available.data["materials"][0]["id"], material.pk)
        self.assertEqual(locked.status_code, status.HTTP_200_OK)
        self.assertFalse(locked.data["is_available"])
        self.assertIsNone(locked.data["content"])
        self.assertEqual(locked.data["materials"], [])

    def test_student_lesson_detail_hides_unavailable_courses(self):
        foreign_course = self.create_course(
            "Foreign Course",
            "FOREIGN-LESSON",
            CourseStatus.PUBLISHED,
        )
        foreign_module = CourseModule.objects.create(
            course=foreign_course,
            title="Foreign Module",
            order=1,
        )
        foreign_topic = CourseTopic.objects.create(
            module=foreign_module,
            title="Foreign Topic",
            order=1,
        )
        foreign_lesson = Lesson.objects.create(
            topic=foreign_topic,
            title="Foreign Lesson",
            order=1,
            is_published=True,
        )
        self.client.force_authenticate(self.student)

        response = self.client.get(self.lesson_detail_url(foreign_lesson))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_enrolled_student_can_download_nested_course_material(self):
        (
            first_lesson,
            _second_lesson,
            material,
            locked_material,
        ) = self.build_student_structure()
        self.client.force_authenticate(self.student)

        with patch.object(
            material.file.storage,
            "open",
            return_value=BytesIO(b"student file"),
        ):
            response = self.client.get(
                reverse(
                    "api-v1:learning-v1:material-download",
                    kwargs={"pk": material.pk},
                )
            )
            content = b"".join(response.streaming_content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content, b"student file")

        locked_response = self.client.get(
            reverse(
                "api-v1:learning-v1:material-download",
                kwargs={"pk": locked_material.pk},
            )
        )
        self.assertEqual(locked_response.status_code, status.HTTP_403_FORBIDDEN)

        completed_at = timezone.now()
        LessonProgress.objects.create(
            student=self.student,
            lesson=first_lesson,
            status=LessonProgressStatus.COMPLETED,
            started_at=completed_at,
            completed_at=completed_at,
        )
        with patch.object(
            locked_material.file.storage,
            "open",
            return_value=BytesIO(b"unlocked student file"),
        ):
            unlocked_response = self.client.get(
                reverse(
                    "api-v1:learning-v1:material-download",
                    kwargs={"pk": locked_material.pk},
                )
            )
            unlocked_content = b"".join(unlocked_response.streaming_content)

        self.assertEqual(unlocked_response.status_code, status.HTTP_200_OK)
        self.assertEqual(unlocked_content, b"unlocked student file")

        self.client.force_authenticate(self.other_student)
        foreign_response = self.client.get(
            reverse(
                "api-v1:learning-v1:material-download",
                kwargs={"pk": material.pk},
            )
        )
        self.assertEqual(foreign_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unavailable_student_course_details_return_not_found(self):
        draft = self.create_course("Draft Course", "DRAFT-2", CourseStatus.DRAFT)
        withdrawn = self.create_course(
            "Withdrawn Course",
            "WITHDRAWN-2",
            CourseStatus.PUBLISHED,
        )
        foreign = self.create_course(
            "Foreign Course",
            "FOREIGN-2",
            CourseStatus.PUBLISHED,
        )
        Enrollment.objects.create(student=self.student, course=draft)
        Enrollment.objects.create(
            student=self.student,
            course=withdrawn,
            status=EnrollmentStatus.WITHDRAWN,
        )
        Enrollment.objects.create(student=self.other_student, course=foreign)
        self.client.force_authenticate(self.student)

        for course in (draft, withdrawn, foreign):
            with self.subTest(course=course.code):
                response = self.client.get(self.detail_url(course))
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_course_api_requires_student_role_and_authentication(self):
        anonymous_response = self.client.get(self.list_url())
        non_student = get_user_model().objects.create_user(username="not-student")
        self.client.force_authenticate(non_student)

        forbidden_response = self.client.get(self.list_url())

        self.assertEqual(
            anonymous_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            forbidden_response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_student_course_routes_have_stable_names(self):
        self.assertEqual(self.list_url(), "/api/v1/student/courses/")
        self.assertEqual(
            self.detail_url(self.published_course),
            f"/api/v1/student/courses/{self.published_course.pk}/",
        )
        first_lesson, _, _, _ = self.build_student_structure()
        self.assertEqual(
            self.lesson_detail_url(first_lesson),
            f"/api/v1/student/lessons/{first_lesson.pk}/",
        )
