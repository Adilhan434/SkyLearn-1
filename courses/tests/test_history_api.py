from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode
from audit.models import (
    CourseHistoryAction,
    CourseHistoryEvent,
    CourseHistoryObjectType,
)
from courses.models import (
    Course,
    CourseTeachingAssignment,
    CourseTeachingRole,
)
from organization.models import DegreeLevel, Department, Faculty, Program, Semester


class CourseHistoryAPITests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.manager = user_model.objects.create_user(
            username="history-manager",
            first_name="History",
            last_name="Manager",
        )
        self.manager.roles.add(Role.objects.get(code=RoleCode.CONTENT_MANAGER))
        self.teacher = user_model.objects.create_user(
            username="history-teacher",
            first_name="Assigned",
            last_name="Teacher",
        )
        self.teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        faculty = Faculty.objects.create(name="Engineering", code="HISTORY-FAC")
        department = Department.objects.create(
            faculty=faculty,
            name="Computer Science",
            code="HISTORY-DEP",
        )
        program = Program.objects.create(
            department=department,
            name="Software Engineering",
            code="HISTORY-PROG",
            degree_level=DegreeLevel.BACHELOR,
        )
        semester = Semester.objects.create(
            name="History API Semester",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        self.course = Course.objects.create(
            title="History API Course",
            code="HISTORY-101",
            credits=5,
            semester=semester,
            faculty=faculty,
            department=department,
            program=program,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=self.teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        )

    def history_url(self, course=None):
        return reverse(
            "api-v1:courses-v1:history",
            kwargs={"pk": (course or self.course).pk},
        )

    def create_event(self, action=CourseHistoryAction.COURSE_CREATED, **overrides):
        values = {
            "course": self.course,
            "action": action,
            "actor": self.manager,
            "object_type": CourseHistoryObjectType.COURSE,
            "object_id": self.course.pk,
            "object_title": self.course.title,
            "details": {"private_internal_value": "not exposed"},
        }
        values.update(overrides)
        return CourseHistoryEvent.objects.create(**values)

    def test_manager_receives_paginated_history_response(self):
        self.create_event(CourseHistoryAction.COURSE_CREATED)
        latest = self.create_event(
            CourseHistoryAction.LESSON_CREATED,
            object_type=CourseHistoryObjectType.LESSON,
            object_id=15,
            object_title="Introduction",
        )
        self.create_event(CourseHistoryAction.PUBLISHED)
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.history_url(), {"page_size": 2})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {"count", "next", "previous", "results"})
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 2)
        result = next(
            item for item in response.data["results"] if item["id"] == latest.pk
        )
        self.assertEqual(
            set(result),
            {"id", "action", "actor", "object", "created_at"},
        )
        self.assertEqual(
            result["actor"],
            {"id": self.manager.pk, "full_name": "History Manager"},
        )
        self.assertEqual(
            result["object"],
            {"type": "lesson", "id": 15, "title": "Introduction"},
        )
        self.assertNotIn("details", result)

    def test_assigned_teacher_can_view_course_history(self):
        event = self.create_event()
        self.client.force_authenticate(self.teacher)

        response = self.client.get(self.history_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["id"], event.pk)

    def test_unassigned_teacher_cannot_discover_foreign_course_history(self):
        foreign_teacher = get_user_model().objects.create_user(
            username="foreign-history-teacher"
        )
        foreign_teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.create_event()
        self.client.force_authenticate(foreign_teacher)

        response = self.client.get(self.history_url())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_history_requires_authentication_and_course_role(self):
        regular_user = get_user_model().objects.create_user(
            username="history-regular-user"
        )

        anonymous_response = self.client.get(self.history_url())
        self.client.force_authenticate(regular_user)
        forbidden_response = self.client.get(self.history_url())

        self.assertEqual(anonymous_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(forbidden_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deleted_actor_is_returned_as_null(self):
        actor = get_user_model().objects.create_user(username="deleted-history-actor")
        event = self.create_event(actor=actor)
        actor.delete()
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.history_url())

        result = next(
            item for item in response.data["results"] if item["id"] == event.pk
        )
        self.assertIsNone(result["actor"])
