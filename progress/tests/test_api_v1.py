from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode
from courses.models import Course, CourseStatus
from enrollments.models import Enrollment, EnrollmentStatus
from learning.models import CourseModule, CourseTopic, Lesson, ReleaseType
from organization.models import DegreeLevel, Department, Faculty, Program, Semester
from progress.models import LessonProgress, LessonProgressStatus


class ProgressAPITests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.student = user_model.objects.create_user(username="progress-student")
        self.student.roles.add(Role.objects.get(code=RoleCode.STUDENT))
        self.other_student = user_model.objects.create_user(username="other-student")
        self.other_student.roles.add(Role.objects.get(code=RoleCode.STUDENT))
        self.non_student = user_model.objects.create_user(username="teacher-no-role")
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
            status=CourseStatus.PUBLISHED,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        Enrollment.objects.create(student=self.student, course=self.course)
        module = CourseModule.objects.create(
            course=self.course,
            title="Module",
            order=1,
        )
        topic = CourseTopic.objects.create(module=module, title="Topic", order=1)
        self.first_lesson = Lesson.objects.create(
            topic=topic,
            title="First lesson",
            order=1,
            is_published=True,
        )
        self.second_lesson = Lesson.objects.create(
            topic=topic,
            title="Second lesson",
            order=2,
            release_type=ReleaseType.AFTER_LESSON,
            required_lesson=self.first_lesson,
            is_published=True,
        )

    @staticmethod
    def lesson_url(action, lesson):
        return reverse(
            f"api-v1:progress-v1:lesson-{action}",
            kwargs={"pk": lesson.pk},
        )

    def course_progress_url(self):
        return reverse(
            "api-v1:progress-v1:course-progress",
            kwargs={"pk": self.course.pk},
        )

    @staticmethod
    def student_progress_url():
        return reverse("api-v1:progress-v1:student-progress")

    def test_progress_routes_match_frontend_contract(self):
        self.assertEqual(
            self.lesson_url("start", self.first_lesson),
            f"/api/v1/student/lessons/{self.first_lesson.pk}/start/",
        )
        self.assertEqual(
            self.lesson_url("complete", self.first_lesson),
            f"/api/v1/student/lessons/{self.first_lesson.pk}/complete/",
        )
        self.assertEqual(self.student_progress_url(), "/api/v1/student/progress/")
        self.assertEqual(
            self.course_progress_url(),
            f"/api/v1/student/courses/{self.course.pk}/progress/",
        )

    def test_start_lesson_is_idempotent(self):
        self.client.force_authenticate(self.student)

        first = self.client.post(self.lesson_url("start", self.first_lesson))
        replay = self.client.post(self.lesson_url("start", self.first_lesson))

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(replay.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["status"], LessonProgressStatus.IN_PROGRESS)
        self.assertEqual(first.data["started_at"], replay.data["started_at"])
        self.assertEqual(LessonProgress.objects.count(), 1)

    def test_start_transitions_existing_not_started_record(self):
        progress = LessonProgress.objects.create(
            student=self.student,
            lesson=self.first_lesson,
        )
        self.client.force_authenticate(self.student)

        response = self.client.post(self.lesson_url("start", self.first_lesson))

        progress.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(progress.status, LessonProgressStatus.IN_PROGRESS)
        self.assertIsNotNone(progress.started_at)
        self.assertIsNone(progress.completed_at)

    def test_start_does_not_regress_completed_lesson(self):
        completed_at = timezone.now()
        progress = LessonProgress.objects.create(
            student=self.student,
            lesson=self.first_lesson,
            status=LessonProgressStatus.COMPLETED,
            started_at=completed_at,
            completed_at=completed_at,
        )
        self.client.force_authenticate(self.student)

        response = self.client.post(self.lesson_url("start", self.first_lesson))

        progress.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(progress.status, LessonProgressStatus.COMPLETED)
        self.assertEqual(progress.started_at, completed_at)
        self.assertEqual(progress.completed_at, completed_at)

    def test_complete_is_idempotent_and_unlocks_required_lesson(self):
        self.client.force_authenticate(self.student)

        first = self.client.post(self.lesson_url("complete", self.first_lesson))
        replay = self.client.post(self.lesson_url("complete", self.first_lesson))
        unlocked = self.client.post(self.lesson_url("complete", self.second_lesson))

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(replay.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["completed_at"], replay.data["completed_at"])
        self.assertEqual(unlocked.status_code, status.HTTP_201_CREATED)
        self.assertEqual(unlocked.data["status"], LessonProgressStatus.COMPLETED)
        self.assertEqual(LessonProgress.objects.count(), 2)

    def test_complete_preserves_existing_started_timestamp(self):
        started_at = timezone.now() - timedelta(minutes=15)
        progress = LessonProgress.objects.create(
            student=self.student,
            lesson=self.first_lesson,
            status=LessonProgressStatus.IN_PROGRESS,
            started_at=started_at,
        )
        self.client.force_authenticate(self.student)

        response = self.client.post(self.lesson_url("complete", self.first_lesson))

        progress.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(progress.status, LessonProgressStatus.COMPLETED)
        self.assertEqual(progress.started_at, started_at)
        self.assertGreaterEqual(progress.completed_at, progress.started_at)

    def test_complete_not_started_sets_both_timestamps(self):
        progress = LessonProgress.objects.create(
            student=self.student,
            lesson=self.first_lesson,
        )
        self.client.force_authenticate(self.student)

        response = self.client.post(self.lesson_url("complete", self.first_lesson))

        progress.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(progress.status, LessonProgressStatus.COMPLETED)
        self.assertIsNotNone(progress.completed_at)
        self.assertEqual(progress.started_at, progress.completed_at)

    def test_complete_requires_active_enrollment(self):
        enrollment = Enrollment.objects.get(student=self.student, course=self.course)
        enrollment.status = EnrollmentStatus.WITHDRAWN
        enrollment.save(update_fields=("status", "updated_at"))
        self.client.force_authenticate(self.student)

        response = self.client.post(self.lesson_url("complete", self.first_lesson))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data["error"]["code"],
            "student_lesson_not_found",
        )
        self.assertFalse(LessonProgress.objects.exists())

    def test_complete_requires_published_course_and_lesson(self):
        self.client.force_authenticate(self.student)
        self.course.status = CourseStatus.DRAFT
        self.course.save(update_fields=("status", "updated_at"))

        draft_response = self.client.post(
            self.lesson_url("complete", self.first_lesson)
        )
        self.course.status = CourseStatus.PUBLISHED
        self.course.save(update_fields=("status", "updated_at"))
        self.first_lesson.is_published = False
        self.first_lesson.save(update_fields=("is_published", "updated_at"))
        unpublished_response = self.client.post(
            self.lesson_url("complete", self.first_lesson)
        )

        self.assertEqual(draft_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(unpublished_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(LessonProgress.objects.exists())

    def test_locked_lesson_cannot_be_started_or_completed(self):
        self.client.force_authenticate(self.student)

        start = self.client.post(self.lesson_url("start", self.second_lesson))
        complete = self.client.post(self.lesson_url("complete", self.second_lesson))

        self.assertEqual(start.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(complete.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(start.data["error"]["code"], "lesson_locked")
        self.assertFalse(LessonProgress.objects.exists())

    def test_locked_complete_does_not_mutate_existing_progress(self):
        started_at = timezone.now()
        progress = LessonProgress.objects.create(
            student=self.student,
            lesson=self.second_lesson,
            status=LessonProgressStatus.IN_PROGRESS,
            started_at=started_at,
        )
        self.client.force_authenticate(self.student)

        response = self.client.post(self.lesson_url("complete", self.second_lesson))

        progress.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(progress.status, LessonProgressStatus.IN_PROGRESS)
        self.assertEqual(progress.started_at, started_at)
        self.assertIsNone(progress.completed_at)

    def test_course_progress_uses_currently_available_lessons(self):
        self.client.force_authenticate(self.student)

        initial = self.client.get(self.course_progress_url())
        self.client.post(self.lesson_url("complete", self.first_lesson))
        partial = self.client.get(self.course_progress_url())
        self.client.post(self.lesson_url("complete", self.second_lesson))
        completed = self.client.get(self.course_progress_url())

        self.assertEqual(
            initial.data,
            {
                "course_id": self.course.pk,
                "total_lessons": 1,
                "completed_lessons": 0,
                "progress_percent": 0,
            },
        )
        self.assertEqual(partial.data["total_lessons"], 2)
        self.assertEqual(partial.data["completed_lessons"], 1)
        self.assertEqual(partial.data["progress_percent"], 50)
        self.assertEqual(completed.data["progress_percent"], 100)

    def test_student_progress_aggregates_accessible_courses(self):
        self.client.force_authenticate(self.student)
        self.client.post(self.lesson_url("complete", self.first_lesson))

        response = self.client.get(self.student_progress_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_courses"], 1)
        self.assertEqual(response.data["total_lessons"], 2)
        self.assertEqual(response.data["completed_lessons"], 1)
        self.assertEqual(response.data["progress_percent"], 50)
        self.assertEqual(response.data["courses"][0]["course_id"], self.course.pk)

    def test_progress_endpoints_enforce_student_access(self):
        anonymous = self.client.get(self.student_progress_url())
        self.client.force_authenticate(self.non_student)
        forbidden = self.client.get(self.student_progress_url())
        self.client.force_authenticate(self.other_student)
        hidden_course = self.client.get(self.course_progress_url())
        hidden_lesson = self.client.post(self.lesson_url("start", self.first_lesson))

        self.assertEqual(anonymous.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(hidden_course.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(hidden_lesson.status_code, status.HTTP_404_NOT_FOUND)
