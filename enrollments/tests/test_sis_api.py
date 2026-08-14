from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode, Student
from courses.models import Course
from enrollments.models import (
    Enrollment,
    EnrollmentSource,
    EnrollmentStatus,
    SISSyncEvent,
    SISSyncResult,
)
from organization.models import DegreeLevel, Department, Faculty, Program, Semester


class SISIntegrationAPITests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(username="sis-admin")
        self.admin.roles.add(Role.objects.get(code=RoleCode.LMS_ADMIN))
        self.student = user_model.objects.create_user(username="sis-student")
        self.student.roles.add(Role.objects.get(code=RoleCode.STUDENT))
        Student.objects.create(student=self.student, id_number="ST-1001")
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
        self.course = Course.objects.create(
            title="Introduction to Programming",
            code="CS101",
            credits=5,
            semester=semester,
            faculty=faculty,
            department=department,
            program=program,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )

    def url(self):
        return reverse("api-v1:sis-integration-v1:enrollment-sync")

    @staticmethod
    def payload(**overrides):
        values = {
            "external_event_id": "evt-123",
            "student_external_id": "ST-1001",
            "course_code": "cs101",
            "action": "enroll",
        }
        values.update(overrides)
        return values

    def test_admin_sync_enrolls_student_from_external_identifiers(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(self.url(), self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        enrollment = Enrollment.objects.get()
        self.assertEqual(enrollment.student, self.student)
        self.assertEqual(enrollment.course, self.course)
        self.assertEqual(enrollment.status, EnrollmentStatus.ACTIVE)
        self.assertEqual(enrollment.source, EnrollmentSource.SIS_SYNC)
        self.assertEqual(enrollment.external_sis_id, "evt-123")
        self.assertEqual(enrollment.created_by, self.admin)
        self.assertEqual(response.data["result"], SISSyncResult.CREATED)
        self.assertFalse(response.data["idempotent_replay"])

    def test_same_external_event_is_idempotent(self):
        self.client.force_authenticate(self.admin)
        first = self.client.post(self.url(), self.payload(), format="json")

        replay = self.client.post(self.url(), self.payload(), format="json")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(replay.status_code, status.HTTP_200_OK)
        self.assertTrue(replay.data["idempotent_replay"])
        self.assertEqual(replay.data["result"], SISSyncResult.CREATED)
        self.assertEqual(Enrollment.objects.count(), 1)
        self.assertEqual(SISSyncEvent.objects.count(), 1)

    def test_reused_event_id_with_different_payload_returns_conflict(self):
        self.client.force_authenticate(self.admin)
        self.client.post(self.url(), self.payload(), format="json")

        response = self.client.post(
            self.url(),
            self.payload(course_code="DIFFERENT"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "sis_event_conflict")
        self.assertEqual(SISSyncEvent.objects.count(), 1)

    def test_distinct_enroll_event_for_active_pair_is_unchanged(self):
        self.client.force_authenticate(self.admin)
        self.client.post(self.url(), self.payload(), format="json")

        response = self.client.post(
            self.url(),
            self.payload(external_event_id="evt-124"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["result"], SISSyncResult.UNCHANGED)
        self.assertEqual(Enrollment.objects.count(), 1)
        enrollment = Enrollment.objects.get()
        self.assertEqual(enrollment.external_sis_id, "evt-124")

    def test_withdraw_and_reenroll_update_single_lifecycle_record(self):
        self.client.force_authenticate(self.admin)
        self.client.post(self.url(), self.payload(), format="json")
        enrollment = Enrollment.objects.get()

        withdrawn = self.client.post(
            self.url(),
            self.payload(external_event_id="evt-200", action="withdraw"),
            format="json",
        )
        enrollment.refresh_from_db()
        self.assertEqual(withdrawn.data["result"], SISSyncResult.WITHDRAWN)
        self.assertEqual(enrollment.status, EnrollmentStatus.WITHDRAWN)

        reenrolled = self.client.post(
            self.url(),
            self.payload(external_event_id="evt-201"),
            format="json",
        )
        enrollment.refresh_from_db()
        self.assertEqual(reenrolled.data["result"], SISSyncResult.REACTIVATED)
        self.assertEqual(enrollment.status, EnrollmentStatus.ACTIVE)
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_distinct_withdraw_event_for_withdrawn_pair_is_unchanged(self):
        self.client.force_authenticate(self.admin)
        self.client.post(self.url(), self.payload(), format="json")
        self.client.post(
            self.url(),
            self.payload(external_event_id="evt-200", action="withdraw"),
            format="json",
        )

        response = self.client.post(
            self.url(),
            self.payload(external_event_id="evt-201", action="withdraw"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["result"], SISSyncResult.UNCHANGED)
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_withdraw_missing_enrollment_returns_stable_not_found(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            self.url(),
            self.payload(action="withdraw"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "enrollment_not_found")
        self.assertFalse(SISSyncEvent.objects.exists())

    def test_unknown_student_or_course_rolls_back_event_claim(self):
        self.client.force_authenticate(self.admin)

        student_response = self.client.post(
            self.url(),
            self.payload(student_external_id="UNKNOWN"),
            format="json",
        )
        course_response = self.client.post(
            self.url(),
            self.payload(external_event_id="evt-404", course_code="UNKNOWN"),
            format="json",
        )

        self.assertEqual(student_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            student_response.data["error"]["code"],
            "sis_student_not_found",
        )
        self.assertEqual(course_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            course_response.data["error"]["code"],
            "sis_course_not_found",
        )
        self.assertFalse(SISSyncEvent.objects.exists())

    def test_external_user_without_student_role_is_not_a_sis_student(self):
        self.client.force_authenticate(self.admin)
        self.student.roles.clear()

        response = self.client.post(self.url(), self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "sis_student_not_found")
        self.assertFalse(SISSyncEvent.objects.exists())

    def test_sync_requires_manage_permission_and_valid_action(self):
        anonymous_response = self.client.post(
            self.url(),
            self.payload(),
            format="json",
        )
        self.client.force_authenticate(self.student)
        forbidden_response = self.client.post(
            self.url(),
            self.payload(),
            format="json",
        )
        self.client.force_authenticate(self.admin)
        invalid_response = self.client.post(
            self.url(),
            self.payload(action="delete"),
            format="json",
        )

        self.assertEqual(
            anonymous_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            forbidden_response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_route_has_stable_name(self):
        self.assertEqual(
            self.url(),
            "/api/v1/integrations/sis/enrollments/sync/",
        )
