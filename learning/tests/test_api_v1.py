from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, RoleCode
from courses.models import (
    Course,
    CourseTeachingAssignment,
    CourseTeachingRole,
)
from learning.models import CourseModule, CourseTopic, Lesson, LessonType, ReleaseType
from organization.models import DegreeLevel, Department, Faculty, Program, Semester


class CourseStructureAPITests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.manager = user_model.objects.create_user(username="structure-manager")
        self.manager.roles.add(Role.objects.get(code=RoleCode.CONTENT_MANAGER))
        self.teacher = user_model.objects.create_user(username="structure-teacher")
        self.teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        faculty = Faculty.objects.create(name="Engineering", code="API-STRUCT-FAC")
        department = Department.objects.create(
            faculty=faculty,
            name="Computer Science",
            code="API-STRUCT-DEP",
        )
        program = Program.objects.create(
            department=department,
            name="Software Engineering",
            code="API-STRUCT-PROG",
            degree_level=DegreeLevel.BACHELOR,
        )
        semester = Semester.objects.create(
            name="API Structure Semester",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        self.course = Course.objects.create(
            title="API Structure Course",
            code="API-STRUCT-101",
            credits=5,
            semester=semester,
            faculty=faculty,
            department=department,
            program=program,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
            created_by=self.manager,
            updated_by=self.manager,
        )
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=self.teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        )
        self.url = reverse(
            "api-v1:courses-v1:structure",
            kwargs={"pk": self.course.pk},
        )

    def create_structure(self):
        second_module = CourseModule.objects.create(
            course=self.course,
            title="Second Module",
            order=2,
            release_type=ReleaseType.AFTER_PREVIOUS,
        )
        first_module = CourseModule.objects.create(
            course=self.course,
            title="First Module",
            order=1,
        )
        second_topic = CourseTopic.objects.create(
            module=first_module,
            title="Second Topic",
            order=2,
        )
        first_topic = CourseTopic.objects.create(
            module=first_module,
            title="First Topic",
            order=1,
        )
        first_lesson = Lesson.objects.create(
            topic=first_topic,
            title="First Lesson",
            lesson_type=LessonType.VIDEO,
            estimated_duration_minutes=20,
            order=1,
            is_published=True,
        )
        second_lesson = Lesson.objects.create(
            topic=first_topic,
            title="Second Lesson",
            lesson_type=LessonType.TEXT,
            order=2,
            release_type=ReleaseType.AFTER_LESSON,
            required_lesson=first_lesson,
        )
        return {
            "first_module": first_module,
            "second_module": second_module,
            "first_topic": first_topic,
            "second_topic": second_topic,
            "first_lesson": first_lesson,
            "second_lesson": second_lesson,
        }

    def test_structure_requires_authentication(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_manager_gets_empty_structure(self):
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {"course_id": self.course.pk, "modules": []},
        )

    def test_returns_nested_structure_in_domain_order(self):
        structure = self.create_structure()
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [module["id"] for module in response.data["modules"]],
            [
                structure["first_module"].pk,
                structure["second_module"].pk,
            ],
        )
        first_module = response.data["modules"][0]
        self.assertEqual(
            [topic["id"] for topic in first_module["topics"]],
            [structure["first_topic"].pk, structure["second_topic"].pk],
        )
        lessons = first_module["topics"][0]["lessons"]
        self.assertEqual(
            [lesson["id"] for lesson in lessons],
            [structure["first_lesson"].pk, structure["second_lesson"].pk],
        )
        self.assertEqual(lessons[0]["lesson_type"], LessonType.VIDEO)
        self.assertEqual(lessons[0]["estimated_duration_minutes"], 20)
        self.assertTrue(lessons[0]["is_published"])
        self.assertEqual(
            lessons[1]["required_lesson"],
            structure["first_lesson"].pk,
        )

    def test_assigned_teacher_can_get_structure(self):
        self.create_structure()
        self.client.force_authenticate(self.teacher)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["course_id"], self.course.pk)

    def test_unassigned_teacher_cannot_get_structure_by_id(self):
        other_teacher = get_user_model().objects.create_user(
            username="unassigned-structure-teacher"
        )
        other_teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.client.force_authenticate(other_teacher)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_cannot_use_staff_structure_endpoint(self):
        student = get_user_model().objects.create_user(username="structure-student")
        student.roles.add(Role.objects.get(code=RoleCode.STUDENT))
        self.client.force_authenticate(student)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_course_returns_not_found(self):
        self.client.force_authenticate(self.manager)

        response = self.client.get(
            reverse(
                "api-v1:courses-v1:structure",
                kwargs={"pk": 999999},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
