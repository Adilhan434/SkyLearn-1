from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode
from courses.models import (
    Course,
    CourseStatus,
    CourseTeachingAssignment,
    CourseTeachingRole,
)
from learning.models import CourseModule, CourseTopic, Lesson
from organization.models import DegreeLevel, Department, Faculty, Program, Semester


class CourseReadinessAPITests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.manager = user_model.objects.create_user(username="readiness-manager")
        self.manager.roles.add(Role.objects.get(code=RoleCode.CONTENT_MANAGER))
        self.teacher = user_model.objects.create_user(username="readiness-teacher")
        self.teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.faculty = Faculty.objects.create(
            name="Readiness Faculty",
            code="READY-FAC",
        )
        department = Department.objects.create(
            faculty=self.faculty,
            name="Readiness Department",
            code="READY-DEP",
        )
        program = Program.objects.create(
            department=department,
            name="Readiness Program",
            code="READY-PROG",
            degree_level=DegreeLevel.BACHELOR,
        )
        semester = Semester.objects.create(
            name="Readiness Semester",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        self.course = Course.objects.create(
            title="Ready Course",
            code="READY-101",
            credits=5,
            semester=semester,
            faculty=self.faculty,
            department=department,
            program=program,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
            created_by=self.manager,
            updated_by=self.manager,
        )
        self.assignment = CourseTeachingAssignment.objects.create(
            course=self.course,
            user=self.teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
            created_by=self.manager,
            updated_by=self.manager,
        )
        self.module = CourseModule.objects.create(
            course=self.course,
            title="Readiness Module",
            order=1,
        )
        self.topic = CourseTopic.objects.create(
            module=self.module,
            title="Readiness Topic",
            order=1,
        )
        self.lesson = Lesson.objects.create(
            topic=self.topic,
            title="Readiness Lesson",
            order=1,
        )
        self.url = reverse(
            "api-v1:courses-v1:readiness",
            kwargs={"pk": self.course.pk},
        )

    def test_readiness_requires_authentication(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_readiness_returns_score_and_checks(self):
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data),
            {"score", "ready_for_review", "checks"},
        )
        self.assertEqual(response.data["score"], 90)
        self.assertTrue(response.data["ready_for_review"])
        checks = {check["key"]: check for check in response.data["checks"]}
        self.assertEqual(checks["metadata"]["status"], "complete")
        self.assertEqual(checks["teacher"]["status"], "complete")
        self.assertEqual(checks["syllabus"]["status"], "warning")
        self.assertEqual(checks["structure"]["status"], "complete")

    def test_syllabus_increases_readiness_score(self):
        self.course.syllabus = "courses/syllabi/ready-course.pdf"
        self.course.save(update_fields=("syllabus",))
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.data["score"], 100)
        syllabus_check = next(
            check
            for check in response.data["checks"]
            if check["key"] == "syllabus"
        )
        self.assertEqual(syllabus_check["status"], "complete")

    def test_missing_primary_teacher_blocks_review(self):
        self.assignment.delete()
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.data["score"], 70)
        self.assertFalse(response.data["ready_for_review"])
        teacher_check = next(
            check
            for check in response.data["checks"]
            if check["key"] == "teacher"
        )
        self.assertEqual(teacher_check["status"], "error")

    def test_missing_structure_blocks_review(self):
        self.module.delete()
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.url)

        self.assertFalse(response.data["ready_for_review"])
        structure_check = next(
            check
            for check in response.data["checks"]
            if check["key"] == "structure"
        )
        self.assertEqual(structure_check["status"], "error")
        self.assertEqual(structure_check["message"], "Course has no modules.")

    def test_topic_without_lessons_blocks_review(self):
        self.lesson.delete()
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.url)

        self.assertFalse(response.data["ready_for_review"])
        structure_check = next(
            check
            for check in response.data["checks"]
            if check["key"] == "structure"
        )
        self.assertIn("topic 1 has no lessons", structure_check["message"])

    def test_module_without_topics_blocks_review(self):
        self.topic.delete()
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.url)

        self.assertFalse(response.data["ready_for_review"])
        structure_check = next(
            check
            for check in response.data["checks"]
            if check["key"] == "structure"
        )
        self.assertIn("Module 1 has no topics.", structure_check["message"])

    def test_inactive_organization_blocks_readiness_and_submit(self):
        self.faculty.is_active = False
        self.faculty.save(update_fields=("is_active",))
        self.client.force_authenticate(self.manager)

        readiness_response = self.client.get(self.url)
        submit_response = self.client.post(
            reverse(
                "api-v1:courses-v1:submit-review",
                kwargs={"pk": self.course.pk},
            )
        )

        self.assertFalse(readiness_response.data["ready_for_review"])
        metadata_check = next(
            check
            for check in readiness_response.data["checks"]
            if check["key"] == "metadata"
        )
        self.assertEqual(metadata_check["status"], "error")
        self.assertIn("Faculty is inactive.", metadata_check["message"])
        self.assertEqual(submit_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            submit_response.data["error"]["code"],
            "course_not_ready",
        )
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, CourseStatus.DRAFT)

    def test_unassigned_teacher_cannot_read_course_readiness(self):
        other_teacher = get_user_model().objects.create_user(
            username="foreign-readiness-teacher"
        )
        other_teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.client.force_authenticate(other_teacher)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
