from datetime import date, timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode
from calendar_events.admin import CalendarEventAdmin
from calendar_events.models import CalendarEvent, CalendarEventType
from courses.models import (
    Course,
    CourseStatus,
    CourseTeachingAssignment,
    CourseTeachingRole,
)
from enrollments.models import Enrollment, EnrollmentStatus
from organization.models import DegreeLevel, Department, Faculty, Program, Semester


class CalendarAPITests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_user(username="calendar-admin")
        self.admin_user.roles.add(Role.objects.get(code=RoleCode.LMS_ADMIN))
        self.teacher = user_model.objects.create_user(username="calendar-teacher")
        self.teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.student = user_model.objects.create_user(username="calendar-student")
        self.student.roles.add(Role.objects.get(code=RoleCode.STUDENT))
        self.other_student = user_model.objects.create_user(username="other-student")
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
        self.course = self.create_course(
            "Introduction to Programming",
            "CS101",
            CourseStatus.PUBLISHED,
            semester,
            faculty,
            department,
            program,
        )
        self.foreign_course = self.create_course(
            "Foreign Course",
            "FOREIGN101",
            CourseStatus.PUBLISHED,
            semester,
            faculty,
            department,
            program,
        )
        self.draft_course = self.create_course(
            "Draft Course",
            "DRAFT101",
            CourseStatus.DRAFT,
            semester,
            faculty,
            department,
            program,
        )
        self.withdrawn_course = self.create_course(
            "Withdrawn Course",
            "WITHDRAWN101",
            CourseStatus.PUBLISHED,
            semester,
            faculty,
            department,
            program,
        )
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=self.teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        )
        Enrollment.objects.create(student=self.student, course=self.course)
        Enrollment.objects.create(
            student=self.other_student, course=self.foreign_course
        )
        Enrollment.objects.create(student=self.student, course=self.draft_course)
        Enrollment.objects.create(
            student=self.student,
            course=self.withdrawn_course,
            status=EnrollmentStatus.WITHDRAWN,
        )
        self.now = timezone.now()
        self.public_event = self.create_event(
            self.course,
            "Public event",
            self.now + timedelta(days=1),
        )
        self.private_event = self.create_event(
            self.course,
            "Private event",
            self.now + timedelta(days=2),
            is_public=False,
        )
        self.foreign_event = self.create_event(
            self.foreign_course,
            "Foreign event",
            self.now + timedelta(days=3),
        )
        self.draft_event = self.create_event(
            self.draft_course,
            "Draft event",
            self.now + timedelta(days=4),
        )
        self.withdrawn_event = self.create_event(
            self.withdrawn_course,
            "Withdrawn event",
            self.now + timedelta(days=5),
        )

    @staticmethod
    def create_course(
        title, code, course_status, semester, faculty, department, program
    ):
        return Course.objects.create(
            title=title,
            code=code,
            credits=5,
            semester=semester,
            faculty=faculty,
            department=department,
            program=program,
            status=course_status,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )

    def create_event(self, course, title, start_at, **overrides):
        values = {
            "course": course,
            "title": title,
            "event_type": CalendarEventType.CUSTOM,
            "start_at": start_at,
            "created_by": self.admin_user,
            "updated_by": self.admin_user,
        }
        values.update(overrides)
        return CalendarEvent.objects.create(**values)

    @staticmethod
    def staff_list_url():
        return reverse("api-v1:calendar-v1:event-list-create")

    @staticmethod
    def student_list_url():
        return reverse("api-v1:student-calendar-v1:event-list")

    @staticmethod
    def detail_url(event):
        return reverse("api-v1:calendar-v1:event-detail", kwargs={"pk": event.pk})

    def test_model_choices_constraint_string_and_admin(self):
        self.assertEqual(
            {value for value, _label in CalendarEventType.choices},
            {
                "course_start",
                "course_end",
                "module_release",
                "lesson_release",
                "custom",
            },
        )
        self.assertEqual(str(self.public_event), "CS101 / Public event")
        self.assertIsInstance(
            admin.site._registry[CalendarEvent],
            CalendarEventAdmin,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_event(
                self.course,
                "Invalid dates",
                self.now,
                end_at=self.now - timedelta(minutes=1),
            )

    def test_admin_can_create_patch_and_delete_event_with_audit_fields(self):
        self.client.force_authenticate(self.admin_user)
        create_response = self.client.post(
            self.staff_list_url(),
            {
                "course": self.course.pk,
                "title": "Course start",
                "description": "Welcome",
                "event_type": CalendarEventType.COURSE_START,
                "start_at": (self.now + timedelta(days=6)).isoformat(),
                "is_public": True,
            },
            format="json",
        )
        event = CalendarEvent.objects.get(title="Course start")
        patch_response = self.client.patch(
            self.detail_url(event),
            {"title": "Updated course start"},
            format="json",
        )
        delete_response = self.client.delete(self.detail_url(event))

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(event.created_by, self.admin_user)
        self.assertEqual(event.updated_by, self.admin_user)
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data["title"], "Updated course start")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CalendarEvent.objects.filter(pk=event.pk).exists())

    def test_staff_api_is_paginated_and_supports_all_filters(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.get(
            self.staff_list_url(),
            {
                "date_from": (self.now + timedelta(hours=12)).date().isoformat(),
                "date_to": (self.now + timedelta(days=2)).date().isoformat(),
                "course": self.course.pk,
                "event_type": CalendarEventType.CUSTOM,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {"count", "next", "previous", "results"})
        self.assertEqual(
            {item["id"] for item in response.data["results"]},
            {self.public_event.pk, self.private_event.pk},
        )

    def test_teacher_is_limited_to_assigned_course_scope(self):
        self.client.force_authenticate(self.teacher)
        response = self.client.get(self.staff_list_url())
        foreign_detail = self.client.get(self.detail_url(self.foreign_event))
        foreign_create = self.client.post(
            self.staff_list_url(),
            {
                "course": self.foreign_course.pk,
                "title": "Forbidden",
                "event_type": CalendarEventType.CUSTOM,
                "start_at": self.now.isoformat(),
            },
            format="json",
        )

        self.assertEqual(
            {item["id"] for item in response.data["results"]},
            {self.public_event.pk, self.private_event.pk},
        )
        self.assertEqual(foreign_detail.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(foreign_create.status_code, status.HTTP_400_BAD_REQUEST)

    def test_event_end_must_not_precede_start(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.post(
            self.staff_list_url(),
            {
                "course": self.course.pk,
                "title": "Invalid",
                "event_type": CalendarEventType.CUSTOM,
                "start_at": self.now.isoformat(),
                "end_at": (self.now - timedelta(minutes=1)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_at", response.data["error"]["fields"])

    def test_student_sees_only_public_active_published_course_events(self):
        self.client.force_authenticate(self.student)

        response = self.client.get(self.student_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.public_event.pk)
        self.assertEqual(response.data["results"][0]["course_code"], "CS101")

    def test_student_calendar_supports_filters(self):
        second = self.create_event(
            self.course,
            "Course ending",
            self.now + timedelta(days=10),
            event_type=CalendarEventType.COURSE_END,
        )
        self.client.force_authenticate(self.student)
        response = self.client.get(
            self.student_list_url(),
            {
                "course": self.course.pk,
                "event_type": CalendarEventType.COURSE_END,
                "date_from": (self.now + timedelta(days=9)).date().isoformat(),
                "date_to": (self.now + timedelta(days=11)).date().isoformat(),
            },
        )

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], second.pk)

    def test_calendar_permissions_reject_wrong_audiences(self):
        anonymous_staff = self.client.get(self.staff_list_url())
        anonymous_student = self.client.get(self.student_list_url())
        self.client.force_authenticate(self.student)
        student_staff = self.client.get(self.staff_list_url())
        self.client.force_authenticate(self.teacher)
        staff_student = self.client.get(self.student_list_url())

        self.assertEqual(anonymous_staff.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(anonymous_student.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(student_staff.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(staff_student.status_code, status.HTTP_403_FORBIDDEN)

    def test_dashboard_contains_only_upcoming_visible_events(self):
        self.create_event(
            self.course,
            "Past event",
            self.now - timedelta(days=1),
        )
        self.client.force_authenticate(self.student)

        response = self.client.get(reverse("api-v1:progress-v1:student-dashboard"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["upcoming_events"]), 1)
        self.assertEqual(
            response.data["upcoming_events"][0]["id"],
            self.public_event.pk,
        )

    def test_routes_match_calendar_contract(self):
        self.assertEqual(self.staff_list_url(), "/api/v1/calendar/events/")
        self.assertEqual(
            self.detail_url(self.public_event),
            f"/api/v1/calendar/events/{self.public_event.pk}/",
        )
        self.assertEqual(self.student_list_url(), "/api/v1/student/calendar/")
