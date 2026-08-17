from datetime import date

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import ForeignKey
from django.test import RequestFactory
from django.test import TestCase

from audit.models import (
    AuditModel,
    CourseHistoryAction,
    CourseHistoryEvent,
    CourseHistoryObjectType,
)
from courses.models import Course
from organization.models import Department, DegreeLevel, Faculty, Program, Semester


class AuditModelTests(TestCase):
    def test_audit_model_is_abstract(self):
        self.assertTrue(AuditModel._meta.abstract)

    def test_release1_model_inherits_all_audit_fields(self):
        field_names = {field.name for field in Faculty._meta.get_fields()}
        self.assertTrue(
            {"created_at", "updated_at", "created_by", "updated_by"}.issubset(
                field_names
            )
        )
        self.assertIsInstance(Faculty._meta.get_field("created_by"), ForeignKey)
        self.assertIsInstance(Faculty._meta.get_field("updated_by"), ForeignKey)

    def test_audit_users_are_optional_and_timestamps_are_automatic(self):
        faculty = Faculty.objects.create(name="Engineering", code="ENG")

        self.assertIsNone(faculty.created_by)
        self.assertIsNone(faculty.updated_by)
        self.assertIsNotNone(faculty.created_at)
        self.assertIsNotNone(faculty.updated_at)

    def test_deleting_user_preserves_domain_record(self):
        user = get_user_model().objects.create_user(
            username="audit-user",
            password="test-password",
        )
        faculty = Faculty.objects.create(
            name="Engineering",
            code="ENG",
            created_by=user,
            updated_by=user,
        )

        user.delete()
        faculty.refresh_from_db()

        self.assertIsNone(faculty.created_by)
        self.assertIsNone(faculty.updated_by)

    def test_admin_mixin_populates_audit_users(self):
        creator = get_user_model().objects.create_superuser(
            username="audit-admin",
            email="audit-admin@example.invalid",
            password="test-password",
        )
        request = RequestFactory().post("/admin/organization/faculty/add/")
        request.user = creator
        faculty = Faculty(name="Engineering", code="ENG")

        admin.site._registry[Faculty].save_model(
            request,
            faculty,
            form=None,
            change=False,
        )

        self.assertEqual(faculty.created_by, creator)
        self.assertEqual(faculty.updated_by, creator)


class CourseHistoryEventTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_user(
            username="history-actor",
            email="history@example.invalid",
            password="test-password",
        )
        faculty = Faculty.objects.create(name="Engineering", code="HIST-FAC")
        department = Department.objects.create(
            faculty=faculty,
            name="Computer Science",
            code="HIST-DEP",
        )
        program = Program.objects.create(
            department=department,
            name="Software Engineering",
            code="HIST-PROG",
            degree_level=DegreeLevel.BACHELOR,
        )
        semester = Semester.objects.create(
            name="History semester",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        cls.course = Course.objects.create(
            title="History Course",
            code="HIST101",
            credits=5,
            semester=semester,
            faculty=faculty,
            department=department,
            program=program,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )

    def test_supports_every_required_release1_action(self):
        self.assertEqual(
            {value for value, _label in CourseHistoryAction.choices},
            {
                "course_created",
                "course_updated",
                "module_created",
                "module_updated",
                "module_deleted",
                "topic_created",
                "topic_updated",
                "topic_deleted",
                "lesson_created",
                "lesson_updated",
                "lesson_deleted",
                "material_uploaded",
                "material_deleted",
                "submitted_for_review",
                "returned_for_revision",
                "published",
                "archived",
                "restored",
                "copied",
            },
        )

    def test_event_keeps_object_snapshot_and_optional_details(self):
        event = CourseHistoryEvent.objects.create(
            course=self.course,
            action=CourseHistoryAction.LESSON_CREATED,
            actor=self.actor,
            object_type=CourseHistoryObjectType.LESSON,
            object_id=15,
            object_title="Introduction",
            details={"module_id": 3},
        )

        self.assertEqual(event.course, self.course)
        self.assertEqual(event.actor, self.actor)
        self.assertEqual(event.details, {"module_id": 3})
        self.assertIsNotNone(event.created_at)
        self.assertEqual(
            str(event),
            "HIST101: lesson_created (lesson:15)",
        )

    def test_deleting_actor_preserves_history(self):
        event = CourseHistoryEvent.objects.create(
            course=self.course,
            action=CourseHistoryAction.COURSE_CREATED,
            actor=self.actor,
            object_type=CourseHistoryObjectType.COURSE,
            object_id=self.course.pk,
            object_title=self.course.title,
        )

        self.actor.delete()
        event.refresh_from_db()

        self.assertIsNone(event.actor)

    def test_model_is_registered_as_read_only_in_admin(self):
        model_admin = admin.site._registry[CourseHistoryEvent]

        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_change_permission(None))
        self.assertFalse(model_admin.has_delete_permission(None))
