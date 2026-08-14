from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode
from courses.models import (
    Course,
    CourseTeachingAssignment,
    CourseTeachingRole,
)
from enrollments.models import Enrollment, EnrollmentSource, EnrollmentStatus
from organization.models import DegreeLevel, Department, Faculty, Program, Semester


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
