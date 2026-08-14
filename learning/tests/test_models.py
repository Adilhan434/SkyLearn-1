from datetime import date, timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from courses.models import Course
from learning.admin import (
    CourseModuleAdmin,
    CourseTopicAdmin,
    LearningMaterialAdmin,
    LessonAdmin,
    PrivateFileInput,
)
from learning.models import (
    CourseModule,
    CourseTopic,
    LearningMaterial,
    LearningMaterialType,
    Lesson,
    LessonType,
    ReleaseType,
)
from organization.models import DegreeLevel, Department, Faculty, Program, Semester


class LearningStructureModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="structure-owner")
        faculty = Faculty.objects.create(name="Engineering", code="STRUCT-FAC")
        department = Department.objects.create(
            faculty=faculty,
            name="Computer Science",
            code="STRUCT-DEP",
        )
        program = Program.objects.create(
            department=department,
            name="Software Engineering",
            code="STRUCT-PROG",
            degree_level=DegreeLevel.BACHELOR,
        )
        semester = Semester.objects.create(
            name="Structure Semester",
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
            "created_by": cls.user,
            "updated_by": cls.user,
        }
        cls.course = Course.objects.create(
            title="Structure Course",
            code="STRUCT-101",
            **course_values,
        )
        cls.other_course = Course.objects.create(
            title="Other Structure Course",
            code="STRUCT-102",
            **course_values,
        )

    def make_module(self, course=None, order=1, **overrides):
        values = {
            "course": course or self.course,
            "title": "Module",
            "order": order,
            "created_by": self.user,
            "updated_by": self.user,
        }
        values.update(overrides)
        return CourseModule.objects.create(**values)

    def make_topic(self, module=None, order=1, **overrides):
        values = {
            "module": module or self.make_module(),
            "title": "Topic",
            "order": order,
            "created_by": self.user,
            "updated_by": self.user,
        }
        values.update(overrides)
        return CourseTopic.objects.create(**values)

    def make_lesson(self, topic=None, order=1, **overrides):
        values = {
            "topic": topic or self.make_topic(),
            "title": "Lesson",
            "lesson_type": LessonType.TEXT,
            "order": order,
            "created_by": self.user,
            "updated_by": self.user,
        }
        values.update(overrides)
        return Lesson.objects.create(**values)

    def test_creates_complete_ordered_hierarchy(self):
        module = self.make_module(title="Foundations")
        topic = self.make_topic(module=module, title="Introduction")
        lesson = self.make_lesson(
            topic=topic,
            title="Welcome",
            estimated_duration_minutes=15,
        )

        self.assertEqual(module.course, self.course)
        self.assertEqual(topic.module, module)
        self.assertEqual(lesson.topic, topic)
        self.assertEqual(lesson.course, self.course)
        self.assertEqual(module.created_by, self.user)
        self.assertEqual(str(module), "STRUCT-101 / 1. Foundations")
        self.assertIn("Introduction", str(topic))
        self.assertIn("Welcome", str(lesson))

    def test_supports_all_release1_lesson_types(self):
        self.assertEqual(
            {value for value, _label in LessonType.choices},
            {"text", "video", "material", "mixed", "external_link"},
        )

    def test_module_order_is_unique_inside_course(self):
        self.make_module(order=1)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_module(order=1, title="Duplicate module order")

    def test_same_module_order_is_allowed_in_another_course(self):
        self.make_module(course=self.course, order=1)
        other_module = self.make_module(course=self.other_course, order=1)

        self.assertEqual(other_module.order, 1)

    def test_topic_and_lesson_order_are_unique_inside_parent(self):
        module = self.make_module()
        topic = self.make_topic(module=module)
        self.make_lesson(topic=topic)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_topic(module=module, title="Duplicate topic")
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_lesson(topic=topic, title="Duplicate lesson")

    def test_orders_must_start_at_one(self):
        module = CourseModule(
            course=self.course,
            title="Invalid module",
            order=0,
        )

        with self.assertRaises(ValidationError):
            module.full_clean()

    def test_date_module_requires_release_at(self):
        module = CourseModule(
            course=self.course,
            title="Scheduled module",
            order=1,
            release_type=ReleaseType.DATE,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "A date-based module requires release_at.",
        ):
            module.full_clean()

        module.release_at = timezone.now() + timedelta(days=1)
        module.full_clean()

    def test_non_date_module_rejects_release_at(self):
        module = CourseModule(
            course=self.course,
            title="Unexpected schedule",
            order=1,
            release_at=timezone.now(),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "release_at is allowed only for date release.",
        ):
            module.full_clean()

    def test_after_lesson_release_requires_prerequisite(self):
        lesson = Lesson(
            topic=self.make_topic(),
            title="Dependent lesson",
            order=1,
            release_type=ReleaseType.AFTER_LESSON,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "An after-lesson release requires required_lesson.",
        ):
            lesson.full_clean()

    def test_required_lesson_must_belong_to_same_course(self):
        required_lesson = self.make_lesson(
            topic=self.make_topic(module=self.make_module(course=self.other_course))
        )
        lesson = Lesson(
            topic=self.make_topic(),
            title="Cross-course dependency",
            order=1,
            release_type=ReleaseType.AFTER_LESSON,
            required_lesson=required_lesson,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "The required lesson must belong to the same course.",
        ):
            lesson.full_clean()

    def test_lesson_cannot_require_itself(self):
        lesson = self.make_lesson()
        lesson.release_type = ReleaseType.AFTER_LESSON
        lesson.required_lesson = lesson

        with self.assertRaisesMessage(
            ValidationError,
            "A lesson cannot require itself.",
        ):
            lesson.full_clean()

    def test_release_dependency_cannot_create_cycle(self):
        topic = self.make_topic()
        first = self.make_lesson(topic=topic, order=1, title="First")
        second = self.make_lesson(
            topic=topic,
            order=2,
            title="Second",
            release_type=ReleaseType.AFTER_LESSON,
            required_lesson=first,
        )
        first.release_type = ReleaseType.AFTER_LESSON
        first.required_lesson = second

        with self.assertRaisesMessage(
            ValidationError,
            "The required lesson would create a dependency cycle.",
        ):
            first.full_clean()

    def test_required_lesson_is_protected_from_deletion(self):
        topic = self.make_topic()
        required_lesson = self.make_lesson(topic=topic, order=1)
        self.make_lesson(
            topic=topic,
            order=2,
            release_type=ReleaseType.AFTER_LESSON,
            required_lesson=required_lesson,
        )

        with self.assertRaises(ProtectedError):
            required_lesson.delete()

    def test_structure_is_deleted_with_course(self):
        module = self.make_module()
        topic = self.make_topic(module=module)
        self.make_lesson(topic=topic)

        self.course.delete()

        self.assertFalse(CourseModule.objects.filter(pk=module.pk).exists())
        self.assertFalse(CourseTopic.objects.filter(pk=topic.pk).exists())
        self.assertFalse(Lesson.objects.exists())

    def test_structure_models_are_registered_in_admin(self):
        self.assertIsInstance(admin.site._registry[CourseModule], CourseModuleAdmin)
        self.assertIsInstance(admin.site._registry[CourseTopic], CourseTopicAdmin)
        self.assertIsInstance(admin.site._registry[Lesson], LessonAdmin)

    def test_creates_learning_material_with_metadata_and_audit(self):
        lesson = self.make_lesson()

        material = LearningMaterial.objects.create(
            lesson=lesson,
            course=self.course,
            title="Course handbook",
            description="Release 1 handbook",
            type=LearningMaterialType.PDF,
            file="learning/materials/handbook.pdf",
            original_filename="handbook.pdf",
            mime_type="application/pdf",
            size=1024,
            extension="pdf",
            download_allowed=True,
            created_by=self.user,
            updated_by=self.user,
        )

        self.assertEqual(material.lesson, lesson)
        self.assertEqual(material.course, self.course)
        self.assertEqual(material.size, 1024)
        self.assertEqual(material.created_by, self.user)
        self.assertIn("Course handbook", str(material))

    def test_supports_all_release1_material_types(self):
        self.assertEqual(
            {value for value, _label in LearningMaterialType.choices},
            {
                "pdf",
                "doc",
                "docx",
                "ppt",
                "pptx",
                "image",
                "audio",
                "video",
                "external_link",
                "library_link",
                "other",
            },
        )

    def test_material_course_must_match_lesson_course(self):
        material = LearningMaterial(
            lesson=self.make_lesson(),
            course=self.other_course,
            title="Foreign material",
            type=LearningMaterialType.OTHER,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Material course must match the lesson course.",
        ):
            material.full_clean()

    def test_learning_material_is_registered_in_admin(self):
        self.assertIsInstance(
            admin.site._registry[LearningMaterial],
            LearningMaterialAdmin,
        )

    def test_private_material_admin_widget_does_not_request_file_url(self):
        widget = PrivateFileInput()

        self.assertFalse(widget.is_initial(object()))
