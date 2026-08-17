from datetime import date, timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from courses.models import Course
from learning.models import CourseModule, CourseTopic, Lesson
from organization.models import DegreeLevel, Department, Faculty, Program, Semester
from progress.admin import LessonProgressAdmin
from progress.models import LessonProgress, LessonProgressStatus


class LessonProgressModelTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.student = user_model.objects.create_user(username="progress-student")
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
        course = Course.objects.create(
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
        module = CourseModule.objects.create(course=course, title="Module", order=1)
        topic = CourseTopic.objects.create(module=module, title="Topic", order=1)
        self.lesson = Lesson.objects.create(topic=topic, title="Lesson", order=1)

    def test_progress_defaults_to_not_started(self):
        progress = LessonProgress.objects.create(
            student=self.student,
            lesson=self.lesson,
        )

        self.assertEqual(progress.status, LessonProgressStatus.NOT_STARTED)
        self.assertIsNone(progress.started_at)
        self.assertIsNone(progress.completed_at)
        self.assertIsNotNone(progress.updated_at)
        self.assertEqual(
            str(progress),
            f"progress-student / lesson {self.lesson.pk} (not_started)",
        )

    def test_student_and_lesson_pair_is_unique(self):
        LessonProgress.objects.create(student=self.student, lesson=self.lesson)

        with self.assertRaises(IntegrityError), transaction.atomic():
            LessonProgress.objects.create(student=self.student, lesson=self.lesson)

    def test_in_progress_requires_started_timestamp(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            LessonProgress.objects.create(
                student=self.student,
                lesson=self.lesson,
                status=LessonProgressStatus.IN_PROGRESS,
            )

    def test_completed_progress_has_consistent_timestamps(self):
        started_at = timezone.now()
        progress = LessonProgress.objects.create(
            student=self.student,
            lesson=self.lesson,
            status=LessonProgressStatus.COMPLETED,
            started_at=started_at,
            completed_at=started_at + timedelta(minutes=10),
        )

        self.assertEqual(progress.status, LessonProgressStatus.COMPLETED)

    def test_completion_cannot_precede_start(self):
        completed_at = timezone.now()

        with self.assertRaises(IntegrityError), transaction.atomic():
            LessonProgress.objects.create(
                student=self.student,
                lesson=self.lesson,
                status=LessonProgressStatus.COMPLETED,
                started_at=completed_at + timedelta(minutes=1),
                completed_at=completed_at,
            )

    def test_progress_is_registered_in_admin(self):
        self.assertIsInstance(
            admin.site._registry[LessonProgress],
            LessonProgressAdmin,
        )
