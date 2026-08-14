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

    def module_create_url(self):
        return reverse(
            "api-v1:courses-v1:module-create",
            kwargs={"course_pk": self.course.pk},
        )

    def reorder_url(self):
        return reverse(
            "api-v1:courses-v1:structure-reorder",
            kwargs={"pk": self.course.pk},
        )

    @staticmethod
    def module_detail_url(module):
        return reverse(
            "api-v1:learning-v1:module-detail",
            kwargs={"pk": module.pk},
        )

    @staticmethod
    def topic_create_url(module):
        return reverse(
            "api-v1:learning-v1:topic-create",
            kwargs={"module_pk": module.pk},
        )

    @staticmethod
    def topic_detail_url(topic):
        return reverse(
            "api-v1:learning-v1:topic-detail",
            kwargs={"pk": topic.pk},
        )

    @staticmethod
    def lesson_create_url(topic):
        return reverse(
            "api-v1:learning-v1:lesson-create",
            kwargs={"topic_pk": topic.pk},
        )

    @staticmethod
    def lesson_detail_url(lesson):
        return reverse(
            "api-v1:learning-v1:lesson-detail",
            kwargs={"pk": lesson.pk},
        )

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

    def test_manager_can_create_module_with_audit_fields(self):
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.module_create_url(),
            {
                "title": "Programming Foundations",
                "description": "Core concepts",
                "order": 1,
                "release_type": ReleaseType.ALWAYS,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        module = CourseModule.objects.get(pk=response.data["id"])
        self.assertEqual(module.course, self.course)
        self.assertEqual(module.created_by, self.manager)
        self.assertEqual(module.updated_by, self.manager)

    def test_create_without_order_appends_module(self):
        CourseModule.objects.create(course=self.course, title="First", order=1)
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.module_create_url(),
            {"title": "Second"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["order"], 2)

    def test_create_rejects_duplicate_order(self):
        CourseModule.objects.create(course=self.course, title="First", order=1)
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.module_create_url(),
            {"title": "Duplicate", "order": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("order", response.data["error"]["fields"])

    def test_create_validates_release_fields(self):
        self.client.force_authenticate(self.manager)

        missing_date_response = self.client.post(
            self.module_create_url(),
            {"title": "Scheduled", "release_type": ReleaseType.DATE},
            format="json",
        )
        invalid_type_response = self.client.post(
            self.module_create_url(),
            {"title": "Invalid", "release_type": ReleaseType.AFTER_LESSON},
            format="json",
        )

        self.assertEqual(
            missing_date_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            invalid_type_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("release_at", missing_date_response.data["error"]["fields"])
        self.assertIn(
            "release_type",
            invalid_type_response.data["error"]["fields"],
        )

    def test_assigned_teacher_can_create_and_patch_draft_module(self):
        self.client.force_authenticate(self.teacher)
        create_response = self.client.post(
            self.module_create_url(),
            {"title": "Teacher Module"},
            format="json",
        )
        module = CourseModule.objects.get(pk=create_response.data["id"])

        patch_response = self.client.patch(
            self.module_detail_url(module),
            {"title": "Updated Teacher Module"},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        module.refresh_from_db()
        self.assertEqual(module.title, "Updated Teacher Module")
        self.assertEqual(module.updated_by, self.teacher)

    def test_unassigned_teacher_cannot_create_module(self):
        teacher = get_user_model().objects.create_user(
            username="foreign-module-teacher"
        )
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.client.force_authenticate(teacher)

        response = self.client.post(
            self.module_create_url(),
            {"title": "Foreign Module"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_teacher_cannot_modify_published_course_structure(self):
        module = CourseModule.objects.create(
            course=self.course,
            title="Published Module",
            order=1,
        )
        self.course.status = "published"
        self.course.save(update_fields=("status",))
        self.client.force_authenticate(self.teacher)

        response = self.client.patch(
            self.module_detail_url(module),
            {"title": "Forbidden update"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_archived_course_structure_cannot_be_changed(self):
        module = CourseModule.objects.create(
            course=self.course,
            title="Archived Module",
            order=1,
        )
        self.course.status = "archived"
        self.course.save(update_fields=("status",))
        self.client.force_authenticate(self.manager)

        create_response = self.client.post(
            self.module_create_url(),
            {"title": "New Module"},
            format="json",
        )
        patch_response = self.client.patch(
            self.module_detail_url(module),
            {"title": "Forbidden update"},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_empty_module_can_be_deleted_without_confirmation(self):
        module = CourseModule.objects.create(
            course=self.course,
            title="Empty Module",
            order=1,
        )
        self.client.force_authenticate(self.manager)

        response = self.client.delete(self.module_detail_url(module))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CourseModule.objects.filter(pk=module.pk).exists())

    def test_non_empty_module_requires_delete_confirmation(self):
        structure = self.create_structure()
        module = structure["first_module"]
        self.client.force_authenticate(self.manager)

        response = self.client.delete(self.module_detail_url(module))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "structure_not_empty")
        self.assertTrue(CourseModule.objects.filter(pk=module.pk).exists())

    def test_confirmed_delete_cascades_nested_structure(self):
        structure = self.create_structure()
        module = structure["first_module"]
        first_topic = structure["first_topic"]
        first_lesson = structure["first_lesson"]
        self.client.force_authenticate(self.manager)

        response = self.client.delete(
            self.module_detail_url(module),
            {"confirm": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CourseModule.objects.filter(pk=module.pk).exists())
        self.assertFalse(CourseTopic.objects.filter(pk=first_topic.pk).exists())
        self.assertFalse(Lesson.objects.filter(pk=first_lesson.pk).exists())

    def test_external_lesson_dependency_blocks_confirmed_module_delete(self):
        structure = self.create_structure()
        first_module = structure["first_module"]
        second_module = structure["second_module"]
        external_topic = CourseTopic.objects.create(
            module=second_module,
            title="External Topic",
            order=1,
        )
        Lesson.objects.create(
            topic=external_topic,
            title="External Dependent Lesson",
            order=1,
            release_type=ReleaseType.AFTER_LESSON,
            required_lesson=structure["first_lesson"],
        )
        self.client.force_authenticate(self.manager)

        response = self.client.delete(
            self.module_detail_url(first_module),
            {"confirm": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "structure_not_empty")
        self.assertTrue(
            CourseModule.objects.filter(pk=first_module.pk).exists()
        )

    def test_module_detail_does_not_expose_unrequired_get(self):
        module = CourseModule.objects.create(
            course=self.course,
            title="No Retrieve Module",
            order=1,
        )
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.module_detail_url(module))

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_manager_can_create_topic_with_audit_fields(self):
        module = CourseModule.objects.create(
            course=self.course,
            title="Topic Parent",
            order=1,
        )
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.topic_create_url(module),
            {
                "title": "Programming Basics",
                "description": "Topic description",
                "order": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        topic = CourseTopic.objects.get(pk=response.data["id"])
        self.assertEqual(topic.module, module)
        self.assertEqual(topic.created_by, self.manager)
        self.assertEqual(topic.updated_by, self.manager)

    def test_create_topic_without_order_appends_to_module(self):
        module = CourseModule.objects.create(
            course=self.course,
            title="Topic Parent",
            order=1,
        )
        CourseTopic.objects.create(module=module, title="First", order=1)
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.topic_create_url(module),
            {"title": "Second"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["order"], 2)

    def test_create_topic_rejects_duplicate_order(self):
        module = CourseModule.objects.create(
            course=self.course,
            title="Topic Parent",
            order=1,
        )
        CourseTopic.objects.create(module=module, title="First", order=1)
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.topic_create_url(module),
            {"title": "Duplicate", "order": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("order", response.data["error"]["fields"])

    def test_assigned_teacher_can_create_and_patch_topic(self):
        module = CourseModule.objects.create(
            course=self.course,
            title="Teacher Topic Parent",
            order=1,
        )
        self.client.force_authenticate(self.teacher)
        create_response = self.client.post(
            self.topic_create_url(module),
            {"title": "Teacher Topic"},
            format="json",
        )
        topic = CourseTopic.objects.get(pk=create_response.data["id"])

        patch_response = self.client.patch(
            self.topic_detail_url(topic),
            {"title": "Updated Teacher Topic"},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        topic.refresh_from_db()
        self.assertEqual(topic.title, "Updated Teacher Topic")
        self.assertEqual(topic.updated_by, self.teacher)

    def test_unassigned_teacher_cannot_create_topic(self):
        module = CourseModule.objects.create(
            course=self.course,
            title="Foreign Topic Parent",
            order=1,
        )
        teacher = get_user_model().objects.create_user(
            username="foreign-topic-teacher"
        )
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.client.force_authenticate(teacher)

        response = self.client.post(
            self.topic_create_url(module),
            {"title": "Foreign Topic"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_archived_course_topic_cannot_be_changed(self):
        module = CourseModule.objects.create(
            course=self.course,
            title="Archived Topic Parent",
            order=1,
        )
        topic = CourseTopic.objects.create(
            module=module,
            title="Archived Topic",
            order=1,
        )
        self.course.status = "archived"
        self.course.save(update_fields=("status",))
        self.client.force_authenticate(self.manager)

        create_response = self.client.post(
            self.topic_create_url(module),
            {"title": "Forbidden Topic"},
            format="json",
        )
        patch_response = self.client.patch(
            self.topic_detail_url(topic),
            {"title": "Forbidden update"},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_empty_topic_can_be_deleted_without_confirmation(self):
        module = CourseModule.objects.create(
            course=self.course,
            title="Empty Topic Parent",
            order=1,
        )
        topic = CourseTopic.objects.create(
            module=module,
            title="Empty Topic",
            order=1,
        )
        self.client.force_authenticate(self.manager)

        response = self.client.delete(self.topic_detail_url(topic))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CourseTopic.objects.filter(pk=topic.pk).exists())

    def test_non_empty_topic_requires_delete_confirmation(self):
        structure = self.create_structure()
        topic = structure["first_topic"]
        self.client.force_authenticate(self.manager)

        response = self.client.delete(self.topic_detail_url(topic))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "structure_not_empty")
        self.assertTrue(CourseTopic.objects.filter(pk=topic.pk).exists())

    def test_confirmed_topic_delete_cascades_internal_dependencies(self):
        structure = self.create_structure()
        topic = structure["first_topic"]
        first_lesson = structure["first_lesson"]
        self.client.force_authenticate(self.manager)

        response = self.client.delete(
            self.topic_detail_url(topic),
            {"confirm": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CourseTopic.objects.filter(pk=topic.pk).exists())
        self.assertFalse(Lesson.objects.filter(pk=first_lesson.pk).exists())

    def test_external_dependency_blocks_confirmed_topic_delete(self):
        structure = self.create_structure()
        source_topic = structure["first_topic"]
        external_topic = structure["second_topic"]
        Lesson.objects.create(
            topic=external_topic,
            title="External Topic Dependency",
            order=1,
            release_type=ReleaseType.AFTER_LESSON,
            required_lesson=structure["first_lesson"],
        )
        self.client.force_authenticate(self.manager)

        response = self.client.delete(
            self.topic_detail_url(source_topic),
            {"confirm": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(CourseTopic.objects.filter(pk=source_topic.pk).exists())

    def test_topic_detail_does_not_expose_unrequired_get(self):
        module = CourseModule.objects.create(
            course=self.course,
            title="No Topic Retrieve Parent",
            order=1,
        )
        topic = CourseTopic.objects.create(
            module=module,
            title="No Topic Retrieve",
            order=1,
        )
        self.client.force_authenticate(self.manager)

        response = self.client.get(self.topic_detail_url(topic))

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_manager_can_create_and_retrieve_lesson(self):
        topic = CourseTopic.objects.create(
            module=CourseModule.objects.create(
                course=self.course,
                title="Lesson Parent Module",
                order=1,
            ),
            title="Lesson Parent Topic",
            order=1,
        )
        self.client.force_authenticate(self.manager)

        create_response = self.client.post(
            self.lesson_create_url(topic),
            {
                "title": "Video Lesson",
                "description": "Lesson description",
                "lesson_type": LessonType.VIDEO,
                "content": "https://video.example/lesson",
                "estimated_duration_minutes": 25,
                "order": 1,
            },
            format="json",
        )
        lesson = Lesson.objects.get(pk=create_response.data["id"])
        detail_response = self.client.get(self.lesson_detail_url(lesson))

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["topic"], topic.pk)
        self.assertEqual(detail_response.data["lesson_type"], LessonType.VIDEO)
        self.assertEqual(lesson.created_by, self.manager)
        self.assertEqual(lesson.updated_by, self.manager)

    def test_create_lesson_without_order_appends_to_topic(self):
        structure = self.create_structure()
        topic = structure["second_topic"]
        Lesson.objects.create(topic=topic, title="First", order=1)
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.lesson_create_url(topic),
            {"title": "Second"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["order"], 2)

    def test_create_lesson_rejects_duplicate_order(self):
        structure = self.create_structure()
        topic = structure["second_topic"]
        Lesson.objects.create(topic=topic, title="First", order=1)
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.lesson_create_url(topic),
            {"title": "Duplicate", "order": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("order", response.data["error"]["fields"])

    def test_create_lesson_validates_types_and_release_fields(self):
        structure = self.create_structure()
        topic = structure["second_topic"]
        self.client.force_authenticate(self.manager)

        invalid_lesson_type = self.client.post(
            self.lesson_create_url(topic),
            {"title": "Invalid Type", "lesson_type": "quiz"},
            format="json",
        )
        missing_date = self.client.post(
            self.lesson_create_url(topic),
            {"title": "Missing Date", "release_type": ReleaseType.DATE},
            format="json",
        )
        missing_required = self.client.post(
            self.lesson_create_url(topic),
            {
                "title": "Missing Required",
                "release_type": ReleaseType.AFTER_LESSON,
            },
            format="json",
        )

        for response in (invalid_lesson_type, missing_date, missing_required):
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "lesson_type",
            invalid_lesson_type.data["error"]["fields"],
        )
        self.assertIn("release_at", missing_date.data["error"]["fields"])
        self.assertIn(
            "required_lesson",
            missing_required.data["error"]["fields"],
        )

    def test_after_lesson_release_accepts_same_course_prerequisite(self):
        structure = self.create_structure()
        topic = structure["second_topic"]
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.lesson_create_url(topic),
            {
                "title": "Dependent Lesson",
                "release_type": ReleaseType.AFTER_LESSON,
                "required_lesson": structure["first_lesson"].pk,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["required_lesson"],
            structure["first_lesson"].pk,
        )

    def test_required_lesson_from_another_course_is_rejected(self):
        structure = self.create_structure()
        topic = structure["second_topic"]
        other_course = Course.objects.create(
            title="Foreign Prerequisite Course",
            code="FOREIGN-LESSON-COURSE",
            credits=self.course.credits,
            semester=self.course.semester,
            faculty=self.course.faculty,
            department=self.course.department,
            program=self.course.program,
            start_date=self.course.start_date,
            end_date=self.course.end_date,
        )
        other_module = CourseModule.objects.create(
            course=other_course,
            title="Foreign Module",
            order=1,
        )
        other_topic = CourseTopic.objects.create(
            module=other_module,
            title="Foreign Topic",
            order=1,
        )
        foreign_lesson = Lesson.objects.create(
            topic=other_topic,
            title="Foreign Lesson",
            order=1,
        )
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.lesson_create_url(topic),
            {
                "title": "Invalid Dependency",
                "release_type": ReleaseType.AFTER_LESSON,
                "required_lesson": foreign_lesson.pk,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("required_lesson", response.data["error"]["fields"])

    def test_patch_rejects_self_dependency_and_cycle(self):
        structure = self.create_structure()
        first = structure["first_lesson"]
        second = structure["second_lesson"]
        self.client.force_authenticate(self.manager)

        self_response = self.client.patch(
            self.lesson_detail_url(first),
            {
                "release_type": ReleaseType.AFTER_LESSON,
                "required_lesson": first.pk,
            },
            format="json",
        )
        cycle_response = self.client.patch(
            self.lesson_detail_url(first),
            {
                "release_type": ReleaseType.AFTER_LESSON,
                "required_lesson": second.pk,
            },
            format="json",
        )

        self.assertEqual(self_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(cycle_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("required_lesson", self_response.data["error"]["fields"])
        self.assertIn("required_lesson", cycle_response.data["error"]["fields"])

    def test_assigned_teacher_can_get_and_patch_lesson(self):
        structure = self.create_structure()
        lesson = structure["first_lesson"]
        self.client.force_authenticate(self.teacher)

        detail_response = self.client.get(self.lesson_detail_url(lesson))
        patch_response = self.client.patch(
            self.lesson_detail_url(lesson),
            {"title": "Teacher Updated Lesson"},
            format="json",
        )

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        lesson.refresh_from_db()
        self.assertEqual(lesson.title, "Teacher Updated Lesson")
        self.assertEqual(lesson.updated_by, self.teacher)

    def test_unassigned_teacher_cannot_get_lesson(self):
        lesson = self.create_structure()["first_lesson"]
        teacher = get_user_model().objects.create_user(
            username="foreign-lesson-teacher"
        )
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.client.force_authenticate(teacher)

        response = self.client.get(self.lesson_detail_url(lesson))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_archived_course_lesson_cannot_be_created_or_patched(self):
        structure = self.create_structure()
        topic = structure["second_topic"]
        lesson = structure["first_lesson"]
        self.course.status = "archived"
        self.course.save(update_fields=("status",))
        self.client.force_authenticate(self.manager)

        create_response = self.client.post(
            self.lesson_create_url(topic),
            {"title": "Forbidden Lesson"},
            format="json",
        )
        patch_response = self.client.patch(
            self.lesson_detail_url(lesson),
            {"title": "Forbidden update"},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_leaf_lesson_can_be_deleted(self):
        structure = self.create_structure()
        lesson = structure["second_lesson"]
        self.client.force_authenticate(self.manager)

        response = self.client.delete(self.lesson_detail_url(lesson))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Lesson.objects.filter(pk=lesson.pk).exists())

    def test_required_lesson_cannot_be_deleted(self):
        structure = self.create_structure()
        lesson = structure["first_lesson"]
        self.client.force_authenticate(self.manager)

        response = self.client.delete(self.lesson_detail_url(lesson))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "lesson_is_required")
        self.assertTrue(Lesson.objects.filter(pk=lesson.pk).exists())

    def test_manager_can_reorder_modules_atomically(self):
        structure = self.create_structure()
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.reorder_url(),
            {
                "type": "module",
                "items": [
                    {"id": structure["second_module"].pk, "order": 1},
                    {"id": structure["first_module"].pk, "order": 2},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [module["id"] for module in response.data["modules"]],
            [structure["second_module"].pk, structure["first_module"].pk],
        )
        structure["second_module"].refresh_from_db()
        structure["first_module"].refresh_from_db()
        self.assertEqual(structure["second_module"].order, 1)
        self.assertEqual(structure["first_module"].order, 2)
        self.assertEqual(structure["first_module"].updated_by, self.manager)

    def test_manager_can_reorder_topics(self):
        structure = self.create_structure()
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.reorder_url(),
            {
                "type": "topic",
                "items": [
                    {"id": structure["second_topic"].pk, "order": 1},
                    {"id": structure["first_topic"].pk, "order": 2},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        topics = response.data["modules"][0]["topics"]
        self.assertEqual(
            [topic["id"] for topic in topics],
            [structure["second_topic"].pk, structure["first_topic"].pk],
        )

    def test_assigned_teacher_can_reorder_lessons(self):
        structure = self.create_structure()
        self.client.force_authenticate(self.teacher)

        response = self.client.post(
            self.reorder_url(),
            {
                "type": "lesson",
                "items": [
                    {"id": structure["second_lesson"].pk, "order": 1},
                    {"id": structure["first_lesson"].pk, "order": 2},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lessons = response.data["modules"][0]["topics"][0]["lessons"]
        self.assertEqual(
            [lesson["id"] for lesson in lessons],
            [structure["second_lesson"].pk, structure["first_lesson"].pk],
        )
        structure["first_lesson"].refresh_from_db()
        self.assertEqual(structure["first_lesson"].updated_by, self.teacher)

    def test_reorder_rejects_duplicate_ids_without_partial_changes(self):
        structure = self.create_structure()
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.reorder_url(),
            {
                "type": "module",
                "items": [
                    {"id": structure["first_module"].pk, "order": 2},
                    {"id": structure["first_module"].pk, "order": 1},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"]["code"], "invalid_structure_order"
        )
        structure["first_module"].refresh_from_db()
        structure["second_module"].refresh_from_db()
        self.assertEqual(structure["first_module"].order, 1)
        self.assertEqual(structure["second_module"].order, 2)

    def test_reorder_rejects_non_contiguous_orders(self):
        structure = self.create_structure()
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.reorder_url(),
            {
                "type": "module",
                "items": [
                    {"id": structure["first_module"].pk, "order": 1},
                    {"id": structure["second_module"].pk, "order": 3},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"]["code"], "invalid_structure_order"
        )

    def test_reorder_requires_complete_sibling_list(self):
        structure = self.create_structure()
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.reorder_url(),
            {
                "type": "module",
                "items": [{"id": structure["first_module"].pk, "order": 1}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"]["code"], "invalid_structure_order"
        )

    def test_reorder_rejects_items_with_different_parents(self):
        structure = self.create_structure()
        foreign_topic = CourseTopic.objects.create(
            module=structure["second_module"],
            title="Other Parent Topic",
            order=1,
        )
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.reorder_url(),
            {
                "type": "topic",
                "items": [
                    {"id": structure["first_topic"].pk, "order": 1},
                    {"id": foreign_topic.pk, "order": 2},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"]["code"], "invalid_structure_order"
        )

    def test_reorder_rejects_item_from_another_course(self):
        structure = self.create_structure()
        other_course = Course.objects.create(
            title="Foreign Reorder Course",
            code="FOREIGN-REORDER",
            credits=self.course.credits,
            semester=self.course.semester,
            faculty=self.course.faculty,
            department=self.course.department,
            program=self.course.program,
            start_date=self.course.start_date,
            end_date=self.course.end_date,
        )
        foreign_module = CourseModule.objects.create(
            course=other_course,
            title="Foreign Module",
            order=1,
        )
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.reorder_url(),
            {
                "type": "module",
                "items": [
                    {"id": structure["first_module"].pk, "order": 1},
                    {"id": foreign_module.pk, "order": 2},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"]["code"], "invalid_structure_order"
        )

    def test_unassigned_teacher_cannot_reorder_structure(self):
        structure = self.create_structure()
        teacher = get_user_model().objects.create_user(
            username="foreign-reorder-teacher"
        )
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.client.force_authenticate(teacher)

        response = self.client.post(
            self.reorder_url(),
            {
                "type": "module",
                "items": [
                    {"id": structure["first_module"].pk, "order": 1},
                    {"id": structure["second_module"].pk, "order": 2},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_archived_course_structure_cannot_be_reordered(self):
        structure = self.create_structure()
        self.course.status = "archived"
        self.course.save(update_fields=("status",))
        self.client.force_authenticate(self.manager)

        response = self.client.post(
            self.reorder_url(),
            {
                "type": "module",
                "items": [
                    {"id": structure["second_module"].pk, "order": 1},
                    {"id": structure["first_module"].pk, "order": 2},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
