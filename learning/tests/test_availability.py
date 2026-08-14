from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from courses.models import Course
from learning.availability import evaluate_lesson_availability
from learning.models import CourseModule, CourseTopic, Lesson, ReleaseType
from organization.models import DegreeLevel, Department, Faculty, Program, Semester


class LessonAvailabilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        faculty = Faculty.objects.create(name="Engineering", code="AVAIL-FAC")
        department = Department.objects.create(
            faculty=faculty,
            name="Computer Science",
            code="AVAIL-DEP",
        )
        program = Program.objects.create(
            department=department,
            name="Software Engineering",
            code="AVAIL-PROG",
            degree_level=DegreeLevel.BACHELOR,
        )
        semester = Semester.objects.create(
            name="Availability Semester",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        cls.course = Course.objects.create(
            title="Availability Course",
            code="AVAIL-101",
            credits=5,
            semester=semester,
            faculty=faculty,
            department=department,
            program=program,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )

    def make_module(self, order=1, **overrides):
        values = {
            "course": self.course,
            "title": f"Module {order}",
            "order": order,
        }
        values.update(overrides)
        return CourseModule.objects.create(**values)

    @staticmethod
    def make_topic(module, order=1):
        return CourseTopic.objects.create(
            module=module,
            title=f"Topic {order}",
            order=order,
        )

    def make_lesson(self, topic, order=1, **overrides):
        values = {
            "topic": topic,
            "title": f"Lesson {order}",
            "order": order,
            "is_published": True,
        }
        values.update(overrides)
        return Lesson.objects.create(**values)

    def test_always_released_published_lesson_is_available(self):
        lesson = self.make_lesson(self.make_topic(self.make_module()))

        availability = evaluate_lesson_availability(lesson)

        self.assertEqual(
            availability.as_dict(),
            {"is_available": True, "lock_reason": None},
        )

    def test_unpublished_lesson_is_locked(self):
        lesson = self.make_lesson(
            self.make_topic(self.make_module()),
            is_published=False,
        )

        availability = evaluate_lesson_availability(lesson)

        self.assertFalse(availability.is_available)
        self.assertEqual(availability.lock_reason, "Lesson is not published.")

    def test_future_module_release_date_locks_lesson(self):
        now = timezone.now()
        module = self.make_module(
            release_type=ReleaseType.DATE,
            release_at=now + timedelta(days=1),
        )
        lesson = self.make_lesson(self.make_topic(module))

        availability = evaluate_lesson_availability(lesson, at=now)

        self.assertFalse(availability.is_available)
        self.assertEqual(
            availability.lock_reason,
            "This module is not available yet.",
        )

    def test_past_module_and_lesson_release_dates_are_available(self):
        now = timezone.now()
        module = self.make_module(
            release_type=ReleaseType.DATE,
            release_at=now - timedelta(days=2),
        )
        lesson = self.make_lesson(
            self.make_topic(module),
            release_type=ReleaseType.DATE,
            release_at=now - timedelta(days=1),
        )

        availability = evaluate_lesson_availability(lesson, at=now)

        self.assertTrue(availability.is_available)

    def test_future_lesson_release_date_locks_lesson(self):
        now = timezone.now()
        lesson = self.make_lesson(
            self.make_topic(self.make_module()),
            release_type=ReleaseType.DATE,
            release_at=now + timedelta(days=1),
        )

        availability = evaluate_lesson_availability(lesson, at=now)

        self.assertFalse(availability.is_available)
        self.assertEqual(
            availability.lock_reason,
            "This lesson is not available yet.",
        )

    def test_after_lesson_requires_completed_prerequisite(self):
        topic = self.make_topic(self.make_module())
        required = self.make_lesson(topic, order=1)
        lesson = self.make_lesson(
            topic,
            order=2,
            release_type=ReleaseType.AFTER_LESSON,
            required_lesson=required,
        )

        locked = evaluate_lesson_availability(lesson)
        available = evaluate_lesson_availability(
            lesson,
            completed_lesson_ids={required.pk},
        )

        self.assertEqual(locked.lock_reason, "Complete the required lesson.")
        self.assertTrue(available.is_available)

    def test_after_previous_requires_previous_lesson_completion(self):
        topic = self.make_topic(self.make_module())
        previous = self.make_lesson(topic, order=1)
        lesson = self.make_lesson(
            topic,
            order=2,
            release_type=ReleaseType.AFTER_PREVIOUS,
        )

        locked = evaluate_lesson_availability(lesson)
        available = evaluate_lesson_availability(
            lesson,
            completed_lesson_ids={previous.pk},
        )

        self.assertEqual(locked.lock_reason, "Complete the previous lesson.")
        self.assertTrue(available.is_available)

    def test_first_lesson_with_after_previous_is_available(self):
        lesson = self.make_lesson(
            self.make_topic(self.make_module()),
            release_type=ReleaseType.AFTER_PREVIOUS,
        )

        availability = evaluate_lesson_availability(lesson)

        self.assertTrue(availability.is_available)

    def test_after_previous_module_requires_all_published_lessons(self):
        first_module = self.make_module(order=1)
        first_topic = self.make_topic(first_module)
        first = self.make_lesson(first_topic, order=1)
        second = self.make_lesson(first_topic, order=2)
        second_module = self.make_module(
            order=2,
            release_type=ReleaseType.AFTER_PREVIOUS,
        )
        target = self.make_lesson(self.make_topic(second_module))

        partially_complete = evaluate_lesson_availability(
            target,
            completed_lesson_ids={first.pk},
        )
        complete = evaluate_lesson_availability(
            target,
            completed_lesson_ids={first.pk, second.pk},
        )

        self.assertEqual(
            partially_complete.lock_reason,
            "Complete the previous module.",
        )
        self.assertTrue(complete.is_available)

    def test_first_after_previous_module_has_no_module_lock(self):
        module = self.make_module(
            release_type=ReleaseType.AFTER_PREVIOUS,
        )
        lesson = self.make_lesson(self.make_topic(module))

        availability = evaluate_lesson_availability(lesson)

        self.assertTrue(availability.is_available)
