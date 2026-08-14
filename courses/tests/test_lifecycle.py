from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode
from courses.models import (
    Course,
    CourseLifecycleAction,
    CourseStatus,
    CourseStatusHistory,
    CourseTeachingAssignment,
    CourseTeachingRole,
)
from organization.models import DegreeLevel, Department, Faculty, Program, Semester


class CourseLifecycleAPITests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.teacher = user_model.objects.create_user(username="lifecycle-teacher")
        self.teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.manager = user_model.objects.create_user(username="lifecycle-manager")
        self.manager.roles.add(Role.objects.get(code=RoleCode.CONTENT_MANAGER))
        self.admin = user_model.objects.create_user(username="lifecycle-admin")
        self.admin.roles.add(Role.objects.get(code=RoleCode.LMS_ADMIN))

        faculty = Faculty.objects.create(name="Engineering", code="LIFE-FAC")
        department = Department.objects.create(
            faculty=faculty,
            name="Computer Science",
            code="LIFE-DEP",
        )
        program = Program.objects.create(
            department=department,
            name="Software Engineering",
            code="LIFE-PROG",
            degree_level=DegreeLevel.BACHELOR,
        )
        semester = Semester.objects.create(
            name="Lifecycle Semester",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        self.course = Course.objects.create(
            title="Lifecycle Course",
            code="LIFE-101",
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
            created_by=self.manager,
            updated_by=self.manager,
        )

    def action_url(self, action):
        return reverse(
            f"api-v1:courses-v1:{action}",
            kwargs={"pk": self.course.pk},
        )

    def test_teacher_can_submit_assigned_draft_for_review(self):
        self.client.force_authenticate(self.teacher)

        response = self.client.post(self.action_url("submit-review"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, CourseStatus.UNDER_REVIEW)
        history = self.course.status_history.get()
        self.assertEqual(history.action, CourseLifecycleAction.SUBMIT_REVIEW)
        self.assertEqual(history.from_status, CourseStatus.DRAFT)
        self.assertEqual(history.to_status, CourseStatus.UNDER_REVIEW)
        self.assertEqual(history.created_by, self.teacher)

    def test_submit_review_requires_active_primary_teacher(self):
        self.course.teaching_assignments.all().delete()
        self.client.force_authenticate(self.manager)

        response = self.client.post(self.action_url("submit-review"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "course_not_ready")
        self.assertEqual(
            response.data["error"]["details"],
            ["Course has no active primary teacher."],
        )
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, CourseStatus.DRAFT)
        self.assertFalse(CourseStatusHistory.objects.exists())

    def test_teacher_cannot_submit_unassigned_course(self):
        self.course.teaching_assignments.all().delete()
        self.client.force_authenticate(self.teacher)

        response = self.client.post(self.action_url("submit-review"))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_transition_has_stable_error_code(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(self.action_url("publish"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"]["code"],
            "invalid_course_transition",
        )

    def test_return_for_revision_requires_comment(self):
        self.course.status = CourseStatus.UNDER_REVIEW
        self.course.save(update_fields=("status",))
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.action_url("return-for-revision"),
            {"comment": "   "},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("comment", response.data["error"]["fields"])

    def test_manager_can_return_course_for_revision(self):
        self.course.status = CourseStatus.UNDER_REVIEW
        self.course.save(update_fields=("status",))
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.action_url("return-for-revision"),
            {"comment": "Add the missing syllabus."},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, CourseStatus.NEEDS_REVISION)
        self.assertEqual(self.course.review_comment, "Add the missing syllabus.")
        self.assertEqual(
            self.course.status_history.get().comment,
            "Add the missing syllabus.",
        )

    def test_teacher_can_edit_and_resubmit_course_needing_revision(self):
        self.course.status = CourseStatus.NEEDS_REVISION
        self.course.review_comment = "Clarify the description."
        self.course.save(update_fields=("status", "review_comment"))
        self.client.force_authenticate(self.teacher)

        update_response = self.client.patch(
            reverse(
                "api-v1:courses-v1:detail",
                kwargs={"pk": self.course.pk},
            ),
            {"description": "Clarified description"},
            format="json",
        )
        submit_response = self.client.post(self.action_url("submit-review"))

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, CourseStatus.UNDER_REVIEW)
        self.assertEqual(self.course.review_comment, "")

    def test_admin_can_publish_under_review_course(self):
        self.course.status = CourseStatus.UNDER_REVIEW
        self.course.save(update_fields=("status",))
        self.client.force_authenticate(self.admin)

        response = self.client.post(self.action_url("publish"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, CourseStatus.PUBLISHED)
        self.assertEqual(self.course.published_by, self.admin)
        self.assertIsNotNone(self.course.published_at)
        self.assertEqual(
            self.course.status_history.get().action,
            CourseLifecycleAction.PUBLISH,
        )

    def test_teacher_cannot_publish_course(self):
        self.course.status = CourseStatus.UNDER_REVIEW
        self.course.save(update_fields=("status",))
        self.client.force_authenticate(self.teacher)

        response = self.client.post(self.action_url("publish"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_archive_and_restore_published_course(self):
        self.course.status = CourseStatus.PUBLISHED
        self.course.published_by = self.admin
        self.course.save(update_fields=("status", "published_by"))
        self.client.force_authenticate(self.admin)

        archive_response = self.client.post(self.action_url("archive"))
        restore_response = self.client.post(self.action_url("restore"))

        self.assertEqual(archive_response.status_code, status.HTTP_200_OK)
        self.assertEqual(restore_response.status_code, status.HTTP_200_OK)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, CourseStatus.PUBLISHED)
        self.assertEqual(
            list(
                self.course.status_history.order_by("created_at").values_list(
                    "action",
                    flat=True,
                )
            ),
            [CourseLifecycleAction.ARCHIVE, CourseLifecycleAction.RESTORE],
        )

    def test_content_manager_without_archive_permission_is_forbidden(self):
        self.course.status = CourseStatus.PUBLISHED
        self.course.save(update_fields=("status",))
        self.client.force_authenticate(self.manager)

        response = self.client.post(self.action_url("archive"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
