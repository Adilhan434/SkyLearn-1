from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import LMSPermission, LMSPermissionCode, Role, RoleCode
from audit.models import (
    CourseHistoryAction,
    CourseHistoryEvent,
    CourseHistoryObjectType,
)
from courses.copying import copy_course
from courses.models import (
    Course,
    CourseStatus,
    CourseTeachingAssignment,
    CourseTeachingRole,
    CourseTemplate,
)
from learning.models import (
    CourseModule,
    CourseTopic,
    LearningMaterial,
    LearningMaterialType,
    Lesson,
    ReleaseType,
    ScormPackage,
    ScormPackageStatus,
)
from organization.models import DegreeLevel, Department, Faculty, Program, Semester


class CourseAPITests(APITestCase):
    list_url = "/api/v1/courses/"

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="course-reader",
            password="test-password",
        )
        self.user.roles.add(Role.objects.get(code=RoleCode.CONTENT_MANAGER))
        self.staff = user_model.objects.create_user(
            username="course-admin",
            password="test-password",
            is_staff=True,
        )
        self.staff.roles.add(Role.objects.get(code=RoleCode.LMS_ADMIN))
        self.faculty = Faculty.objects.create(name="Engineering", code="ENG")
        self.other_faculty = Faculty.objects.create(name="Business", code="BUS")
        self.department = Department.objects.create(
            faculty=self.faculty,
            name="Computer Science",
            code="CS",
        )
        self.program = Program.objects.create(
            department=self.department,
            name="Software Engineering",
            code="SE",
            degree_level=DegreeLevel.BACHELOR,
        )
        self.semester = Semester.objects.create(
            name="Fall 2026",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 20),
        )
        self.other_semester = Semester.objects.create(
            name="Spring 2027",
            start_date=date(2027, 1, 15),
            end_date=date(2027, 5, 30),
        )
        self.course = self.create_course()

    def create_course(self, **overrides):
        index = Course.objects.count() + 1
        values = {
            "title": f"Introduction to Programming {index}",
            "code": f"CS{index:03d}",
            "description": "Programming foundations",
            "credits": 5,
            "semester": self.semester,
            "faculty": self.faculty,
            "department": self.department,
            "program": self.program,
            "status": CourseStatus.DRAFT,
            "start_date": date(2026, 9, 1),
            "end_date": date(2026, 12, 20),
            "created_by": self.staff,
            "updated_by": self.staff,
        }
        values.update(overrides)
        return Course.objects.create(**values)

    def valid_payload(self, **overrides):
        values = {
            "title": "Data Structures",
            "code": "CS201",
            "description": "Core data structures",
            "language": "en",
            "credits": 5,
            "semester": self.semester.pk,
            "faculty": self.faculty.pk,
            "department": self.department.pk,
            "program": self.program.pk,
            "status": CourseStatus.DRAFT,
            "start_date": "2026-09-01",
            "end_date": "2026-12-20",
        }
        values.update(overrides)
        return values

    def copy_url(self, course=None):
        return reverse(
            "api-v1:courses-v1:copy",
            kwargs={"pk": (course or self.course).pk},
        )

    def template_list_url(self):
        return reverse("api-v1:course-templates-v1:list-create")

    def template_detail_url(self, template):
        return reverse(
            "api-v1:course-templates-v1:detail",
            kwargs={"pk": template.pk},
        )

    def template_create_course_url(self, template):
        return reverse(
            "api-v1:course-templates-v1:create-course",
            kwargs={"pk": template.pk},
        )

    def create_template(self, **overrides):
        payload = {
            "title": "Programming template",
            "description": "Reusable structure",
            "source_course": self.course.pk,
        }
        payload.update(overrides)
        self.client.force_authenticate(self.user)
        return self.client.post(self.template_list_url(), payload, format="json")

    def build_copy_structure(self):
        first_module = CourseModule.objects.create(
            course=self.course,
            title="Foundations",
            description="Module description",
            order=1,
        )
        dated_module = CourseModule.objects.create(
            course=self.course,
            title="Advanced",
            order=2,
            release_type=ReleaseType.DATE,
            release_at=timezone.now(),
        )
        topic = CourseTopic.objects.create(
            module=first_module,
            title="Introduction",
            description="Topic description",
            order=1,
        )
        first_lesson = Lesson.objects.create(
            topic=topic,
            title="First lesson",
            content="Lesson content",
            order=1,
            is_published=True,
        )
        second_lesson = Lesson.objects.create(
            topic=topic,
            title="Second lesson",
            order=2,
            release_type=ReleaseType.AFTER_LESSON,
            required_lesson=first_lesson,
            is_published=True,
        )
        LearningMaterial.objects.create(
            lesson=first_lesson,
            course=self.course,
            title="Handbook",
            type=LearningMaterialType.PDF,
            file="learning/materials/handbook.pdf",
            original_filename="handbook.pdf",
            mime_type="application/pdf",
            size=100,
            extension="pdf",
            created_by=self.staff,
            updated_by=self.staff,
        )
        ScormPackage.objects.create(
            lesson=first_lesson,
            course=self.course,
            title="SCORM source",
            file="learning/scorm/source.zip",
            version="1.2",
            launch_path="index.html",
            status=ScormPackageStatus.READY,
        )
        return dated_module, first_lesson, second_lesson

    def test_list_requires_authentication(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_gets_paginated_compact_list(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data),
            {"count", "next", "previous", "results"},
        )
        self.assertEqual(response.data["count"], 1)
        item = response.data["results"][0]
        self.assertEqual(
            set(item),
            {
                "id",
                "title",
                "code",
                "status",
                "language",
                "credits",
                "semester",
                "teacher",
                "faculty",
                "department",
                "program",
                "cover",
                "start_date",
                "end_date",
                "updated_at",
            },
        )
        self.assertEqual(item["semester"]["name"], "Fall 2026")
        self.assertEqual(item["faculty"]["code"], "ENG")
        self.assertIsNone(item["teacher"])

    def test_list_is_paginated(self):
        for number in range(2, 23):
            self.create_course(code=f"CS{number:03d}")
        self.client.force_authenticate(self.user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.data["count"], 22)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])

    def test_search_matches_title_and_code(self):
        self.create_course(title="Database Systems", code="DB301")
        self.client.force_authenticate(self.user)

        title_response = self.client.get(self.list_url, {"search": "Database"})
        code_response = self.client.get(self.list_url, {"search": "DB301"})

        self.assertEqual(title_response.data["count"], 1)
        self.assertEqual(code_response.data["count"], 1)

    def test_search_matches_description_and_teacher_full_name(self):
        teacher = get_user_model().objects.create_user(
            username="searchable-teacher",
            first_name="Ada",
            last_name="Lovelace",
        )
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        searchable_course = self.create_course(
            code="SEARCH-COURSE",
            description="Distributed computing concepts",
        )
        CourseTeachingAssignment.objects.create(
            course=searchable_course,
            user=teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        )
        self.client.force_authenticate(self.user)

        description_response = self.client.get(
            self.list_url,
            {"search": "distributed"},
        )
        teacher_response = self.client.get(
            self.list_url,
            {"search": "Ada Lovelace"},
        )

        self.assertEqual(description_response.data["count"], 1)
        self.assertEqual(teacher_response.data["count"], 1)
        self.assertEqual(
            teacher_response.data["results"][0]["id"],
            searchable_course.pk,
        )

    def test_search_does_not_treat_assistant_as_teacher(self):
        assistant = get_user_model().objects.create_user(
            username="searchable-assistant",
            first_name="Unique",
            last_name="AssistantName",
        )
        assistant.roles.add(
            Role.objects.get(code=RoleCode.TEACHING_ASSISTANT)
        )
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=assistant,
            role=CourseTeachingRole.TEACHING_ASSISTANT,
        )
        self.client.force_authenticate(self.user)

        response = self.client.get(
            self.list_url,
            {"search": "AssistantName"},
        )

        self.assertEqual(response.data["count"], 0)

    def test_filters_by_status_semester_and_faculty(self):
        self.create_course(
            code="CS-PUB",
            status=CourseStatus.PUBLISHED,
            semester=self.other_semester,
        )
        self.client.force_authenticate(self.user)

        status_response = self.client.get(
            self.list_url, {"status": CourseStatus.PUBLISHED}
        )
        semester_response = self.client.get(
            self.list_url, {"semester": self.other_semester.pk}
        )
        faculty_response = self.client.get(
            self.list_url, {"faculty": self.other_faculty.pk}
        )

        self.assertEqual(status_response.data["count"], 1)
        self.assertEqual(semester_response.data["count"], 1)
        self.assertEqual(faculty_response.data["count"], 0)

    def test_filters_by_department_program_language_and_creator(self):
        self.create_course(
            code="RU-COURSE",
            language="ru",
            created_by=self.user,
            updated_by=self.user,
        )
        self.client.force_authenticate(self.user)

        department_response = self.client.get(
            self.list_url,
            {"department": self.department.pk},
        )
        program_response = self.client.get(
            self.list_url,
            {"program": self.program.pk},
        )
        language_response = self.client.get(
            self.list_url,
            {"language": "ru"},
        )
        creator_response = self.client.get(
            self.list_url,
            {"created_by": self.user.pk},
        )

        self.assertEqual(department_response.data["count"], 2)
        self.assertEqual(program_response.data["count"], 2)
        self.assertEqual(language_response.data["count"], 1)
        self.assertEqual(creator_response.data["count"], 1)

    def test_filters_by_assigned_teacher_not_assistant(self):
        teacher = get_user_model().objects.create_user(username="filter-teacher")
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        assistant = get_user_model().objects.create_user(
            username="filter-assistant"
        )
        assistant.roles.add(
            Role.objects.get(code=RoleCode.TEACHING_ASSISTANT)
        )
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        )
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=assistant,
            role=CourseTeachingRole.TEACHING_ASSISTANT,
        )
        self.client.force_authenticate(self.user)

        teacher_response = self.client.get(
            self.list_url,
            {"teacher": teacher.pk},
        )
        assistant_response = self.client.get(
            self.list_url,
            {"teacher": assistant.pk},
        )

        self.assertEqual(teacher_response.data["count"], 1)
        self.assertEqual(assistant_response.data["count"], 0)

    def test_list_supports_ordering(self):
        first_alphabetically = self.create_course(
            title="Algorithms",
            code="ZZ-COURSE",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
        )
        self.create_course(title="Zoology", code="AA-COURSE")
        self.client.force_authenticate(self.user)

        title_response = self.client.get(self.list_url, {"ordering": "title"})
        start_date_response = self.client.get(
            self.list_url,
            {"ordering": "start_date"},
        )
        descending_code_response = self.client.get(
            self.list_url,
            {"ordering": "-code"},
        )

        self.assertEqual(
            [item["title"] for item in title_response.data["results"]],
            sorted(
                item["title"] for item in title_response.data["results"]
            ),
        )
        self.assertEqual(
            start_date_response.data["results"][0]["id"],
            first_alphabetically.pk,
        )
        self.assertEqual(
            descending_code_response.data["results"][0]["code"],
            "ZZ-COURSE",
        )

    def test_list_supports_page_and_page_size(self):
        for number in range(2, 6):
            self.create_course(code=f"PAGE-{number}")
        self.client.force_authenticate(self.user)

        response = self.client.get(
            self.list_url,
            {"page": 2, "page_size": 2},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 5)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["previous"])
        self.assertIsNotNone(response.data["next"])

    def test_invalid_choice_filter_returns_validation_error(self):
        self.client.force_authenticate(self.user)

        response = self.client.get(self.list_url, {"language": "invalid"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("language", response.data["error"]["fields"])

    def test_regular_user_cannot_create_course(self):
        regular_user = get_user_model().objects.create_user(
            username="course-user-without-role"
        )
        self.client.force_authenticate(regular_user)

        response = self.client.post(self.list_url, self.valid_payload())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_without_management_role_cannot_list_courses(self):
        user = get_user_model().objects.create_user(username="plain-course-user")
        self.client.force_authenticate(user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_use_staff_course_api(self):
        student = get_user_model().objects.create_user(username="course-student")
        student.roles.add(Role.objects.get(code=RoleCode.STUDENT))
        self.client.force_authenticate(student)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_list_contains_only_assigned_courses(self):
        teacher = get_user_model().objects.create_user(
            username="course-teacher",
            first_name="Teacher",
            last_name="Demo",
        )
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.create_course(code="UNASSIGNED-COURSE")
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        )
        self.client.force_authenticate(teacher)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.course.pk)
        self.assertEqual(
            response.data["results"][0]["teacher"],
            {"id": teacher.pk, "full_name": "Teacher Demo"},
        )

    def test_assistant_list_contains_only_assigned_courses(self):
        assistant = get_user_model().objects.create_user(
            username="course-assistant"
        )
        assistant.roles.add(
            Role.objects.get(code=RoleCode.TEACHING_ASSISTANT)
        )
        self.create_course(code="ASSISTANT-UNASSIGNED")
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=assistant,
            role=CourseTeachingRole.TEACHING_ASSISTANT,
        )
        self.client.force_authenticate(assistant)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.course.pk)

    def test_teacher_cannot_retrieve_unassigned_course_by_id(self):
        teacher = get_user_model().objects.create_user(
            username="unassigned-course-teacher"
        )
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.client.force_authenticate(teacher)

        response = self.client.get(f"{self.list_url}{self.course.pk}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_staff_can_create_course_and_is_recorded_as_creator(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(self.list_url, self.valid_payload())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Course.objects.get(code="CS201")
        self.assertEqual(created.created_by, self.staff)
        self.assertEqual(created.updated_by, self.staff)
        event = CourseHistoryEvent.objects.get(
            course=created,
            action=CourseHistoryAction.COURSE_CREATED,
        )
        self.assertEqual(event.actor, self.staff)
        self.assertEqual(event.object_type, CourseHistoryObjectType.COURSE)
        self.assertEqual(event.object_id, created.pk)
        self.assertEqual(event.object_title, created.title)

    def test_create_normalizes_course_code(self):
        self.client.force_authenticate(self.staff)

        response = self.client.post(
            self.list_url,
            self.valid_payload(code="  cs-201  "),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Course.objects.filter(code="CS-201").exists())

    def test_create_rejects_case_insensitive_duplicate_code(self):
        self.client.force_authenticate(self.staff)

        response = self.client.post(
            self.list_url,
            self.valid_payload(code=self.course.code.lower()),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("code", response.data["error"]["fields"])

    def test_create_requires_non_blank_title_and_code(self):
        self.client.force_authenticate(self.staff)
        missing_payload = self.valid_payload()
        missing_payload.pop("title")
        missing_payload.pop("code")

        missing_response = self.client.post(
            self.list_url,
            missing_payload,
        )
        blank_response = self.client.post(
            self.list_url,
            self.valid_payload(title="   ", code="   "),
        )

        self.assertEqual(missing_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(blank_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", missing_response.data["error"]["fields"])
        self.assertIn("code", missing_response.data["error"]["fields"])
        self.assertIn("title", blank_response.data["error"]["fields"])
        self.assertIn("code", blank_response.data["error"]["fields"])

    def test_create_rejects_credits_outside_supported_range(self):
        self.client.force_authenticate(self.staff)

        zero_response = self.client.post(
            self.list_url,
            self.valid_payload(credits=0),
        )
        excessive_response = self.client.post(
            self.list_url,
            self.valid_payload(credits=61),
        )

        self.assertEqual(zero_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(excessive_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("credits", zero_response.data["error"]["fields"])
        self.assertIn("credits", excessive_response.data["error"]["fields"])

    def test_create_rejects_unknown_semester(self):
        self.client.force_authenticate(self.staff)

        response = self.client.post(
            self.list_url,
            self.valid_payload(semester=999999),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("semester", response.data["error"]["fields"])

    def test_create_rejects_inactive_organization_objects(self):
        self.faculty.is_active = False
        self.faculty.save(update_fields=("is_active",))
        self.department.is_active = False
        self.department.save(update_fields=("is_active",))
        self.program.is_active = False
        self.program.save(update_fields=("is_active",))
        self.client.force_authenticate(self.staff)

        response = self.client.post(self.list_url, self.valid_payload())

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            set(response.data["error"]["fields"]),
            {"faculty", "department", "program"},
        )

    def test_content_manager_can_assign_primary_teacher_on_create(self):
        teacher = get_user_model().objects.create_user(username="selected-teacher")
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.client.force_authenticate(self.user)

        response = self.client.post(
            self.list_url,
            self.valid_payload(teacher=teacher.pk),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Course.objects.get(code="CS201")
        assignment = created.teaching_assignments.get(user=teacher)
        self.assertTrue(assignment.is_primary)
        self.assertEqual(assignment.created_by, self.user)

    def test_create_rejects_inactive_teacher(self):
        teacher = get_user_model().objects.create_user(
            username="inactive-selected-teacher",
            is_active=False,
        )
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.client.force_authenticate(self.user)

        response = self.client.post(
            self.list_url,
            self.valid_payload(teacher=teacher.pk),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("teacher", response.data["error"]["fields"])

    def test_create_rejects_user_without_teacher_role(self):
        non_teacher = get_user_model().objects.create_user(
            username="selected-non-teacher"
        )
        self.client.force_authenticate(self.user)

        response = self.client.post(
            self.list_url,
            self.valid_payload(teacher=non_teacher.pk),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("teacher", response.data["error"]["fields"])

    def test_teacher_can_create_course_and_becomes_primary_teacher(self):
        teacher = get_user_model().objects.create_user(username="creating-teacher")
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.client.force_authenticate(teacher)

        response = self.client.post(self.list_url, self.valid_payload())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Course.objects.get(code="CS201")
        assignment = created.teaching_assignments.get(user=teacher)
        self.assertEqual(assignment.role, CourseTeachingRole.TEACHER)
        self.assertTrue(assignment.is_primary)

    def test_assistant_cannot_create_course(self):
        assistant = get_user_model().objects.create_user(
            username="creating-assistant"
        )
        assistant.roles.add(
            Role.objects.get(code=RoleCode.TEACHING_ASSISTANT)
        )
        self.client.force_authenticate(assistant)

        response = self.client.post(self.list_url, self.valid_payload())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_validates_organization_relationships(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(
            self.list_url,
            self.valid_payload(faculty=self.other_faculty.pk),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("department", response.data["error"]["fields"])

    def test_authenticated_user_can_retrieve_course(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(f"{self.list_url}{self.course.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.course.pk)
        self.assertEqual(response.data["code"], self.course.code)

    def test_content_manager_can_patch_course_and_updates_actor(self):
        self.client.force_authenticate(self.user)

        response = self.client.patch(
            f"{self.list_url}{self.course.pk}/",
            {"title": "Updated Course"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.course.refresh_from_db()
        self.assertEqual(self.course.title, "Updated Course")
        self.assertEqual(self.course.updated_by, self.user)
        event = CourseHistoryEvent.objects.get(
            course=self.course,
            action=CourseHistoryAction.COURSE_UPDATED,
        )
        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.object_title, "Updated Course")
        self.assertEqual(event.details, {"changed_fields": ["title"]})

    def test_empty_patch_does_not_create_course_updated_event(self):
        self.client.force_authenticate(self.user)

        response = self.client.patch(
            f"{self.list_url}{self.course.pk}/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            self.course.history_events.filter(
                action=CourseHistoryAction.COURSE_UPDATED,
            ).exists()
        )

    def test_patch_validates_dates_against_existing_values(self):
        self.client.force_authenticate(self.user)

        response = self.client.patch(
            f"{self.list_url}{self.course.pk}/",
            {"start_date": "2027-01-01"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_date", response.data["error"]["fields"])

    def test_patch_replaces_primary_teacher(self):
        first_teacher = get_user_model().objects.create_user(
            username="first-primary-teacher"
        )
        second_teacher = get_user_model().objects.create_user(
            username="second-primary-teacher"
        )
        teacher_role = Role.objects.get(code=RoleCode.TEACHER)
        first_teacher.roles.add(teacher_role)
        second_teacher.roles.add(teacher_role)
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=first_teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        )
        self.client.force_authenticate(self.user)

        response = self.client.patch(
            f"{self.list_url}{self.course.pk}/",
            {"teacher": second_teacher.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        first_assignment = self.course.teaching_assignments.get(user=first_teacher)
        second_assignment = self.course.teaching_assignments.get(user=second_teacher)
        self.assertFalse(first_assignment.is_primary)
        self.assertTrue(second_assignment.is_primary)

    def test_teacher_can_patch_assigned_draft_course(self):
        teacher = get_user_model().objects.create_user(username="editing-teacher")
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        )
        self.client.force_authenticate(teacher)

        response = self.client.patch(
            f"{self.list_url}{self.course.pk}/",
            {"description": "Teacher update"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.course.refresh_from_db()
        self.assertEqual(self.course.description, "Teacher update")
        self.assertEqual(self.course.updated_by, teacher)

    def test_teacher_cannot_patch_assigned_under_review_course(self):
        self.course.status = CourseStatus.UNDER_REVIEW
        self.course.save(update_fields=("status",))
        teacher = get_user_model().objects.create_user(
            username="review-course-teacher"
        )
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        )
        self.client.force_authenticate(teacher)

        response = self.client.patch(
            f"{self.list_url}{self.course.pk}/",
            {"title": "Forbidden update"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.course.refresh_from_db()
        self.assertNotEqual(self.course.title, "Forbidden update")

    def test_teacher_cannot_patch_unassigned_course(self):
        teacher = get_user_model().objects.create_user(
            username="foreign-edit-teacher"
        )
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.client.force_authenticate(teacher)

        response = self.client.patch(
            f"{self.list_url}{self.course.pk}/",
            {"title": "Foreign update"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_assistant_cannot_patch_course_without_edit_permission(self):
        assistant = get_user_model().objects.create_user(username="edit-assistant")
        assistant.roles.add(
            Role.objects.get(code=RoleCode.TEACHING_ASSISTANT)
        )
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=assistant,
            role=CourseTeachingRole.TEACHING_ASSISTANT,
        )
        self.client.force_authenticate(assistant)

        response = self.client.patch(
            f"{self.list_url}{self.course.pk}/",
            {"title": "Assistant update"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_patch_cannot_change_course_status(self):
        self.client.force_authenticate(self.user)

        response = self.client.patch(
            f"{self.list_url}{self.course.pk}/",
            {"status": CourseStatus.PUBLISHED},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, CourseStatus.DRAFT)

    def test_archived_course_cannot_be_patched(self):
        self.course.status = CourseStatus.ARCHIVED
        self.course.save(update_fields=("status",))
        self.client.force_authenticate(self.staff)

        response = self.client.patch(
            f"{self.list_url}{self.course.pk}/",
            {"title": "Archived update"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_content_manager_can_delete_draft_course(self):
        self.client.force_authenticate(self.user)

        response = self.client.delete(f"{self.list_url}{self.course.pk}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Course.objects.filter(pk=self.course.pk).exists())

    def test_published_course_cannot_be_permanently_deleted(self):
        self.course.status = CourseStatus.PUBLISHED
        self.course.save(update_fields=("status",))
        self.client.force_authenticate(self.user)

        response = self.client.delete(f"{self.list_url}{self.course.pk}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Course.objects.filter(pk=self.course.pk).exists())

    def test_teacher_cannot_delete_course_without_delete_permission(self):
        teacher = get_user_model().objects.create_user(
            username="deleting-teacher"
        )
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        )
        self.client.force_authenticate(teacher)

        response = self.client.delete(f"{self.list_url}{self.course.pk}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_put_is_not_supported(self):
        self.client.force_authenticate(self.user)

        response = self.client.put(
            f"{self.list_url}{self.course.pk}/",
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_unknown_course_returns_not_found(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(f"{self.list_url}999999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_content_manager_copies_course_content_into_new_draft(self):
        dated_module, first_lesson, second_lesson = self.build_copy_structure()
        teacher = get_user_model().objects.create_user(username="copy-teacher")
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        )
        published_at = timezone.now()
        self.course.status = CourseStatus.PUBLISHED
        self.course.review_comment = "Source review"
        self.course.published_at = published_at
        self.course.published_by = self.staff
        self.course.cover = "courses/covers/source.png"
        self.course.syllabus = "courses/syllabi/source.pdf"
        self.course.save()
        self.client.force_authenticate(self.user)

        response = self.client.post(
            self.copy_url(),
            {"title": "Programming Copy", "code": "copy-2027"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        copied = Course.objects.get(pk=response.data["id"])
        self.assertEqual(copied.title, "Programming Copy")
        self.assertEqual(copied.code, "COPY-2027")
        self.assertEqual(copied.status, CourseStatus.DRAFT)
        self.assertEqual(copied.description, self.course.description)
        self.assertEqual(copied.cover.name, self.course.cover.name)
        self.assertEqual(copied.syllabus.name, self.course.syllabus.name)
        self.assertEqual(copied.review_comment, "")
        self.assertIsNone(copied.published_at)
        self.assertIsNone(copied.published_by)
        self.assertEqual(copied.created_by, self.user)
        self.assertEqual(copied.updated_by, self.user)
        self.assertEqual(copied.modules.count(), 2)

        copied_dated_module = copied.modules.get(order=dated_module.order)
        self.assertEqual(copied_dated_module.release_type, ReleaseType.DATE)
        self.assertEqual(copied_dated_module.release_at, dated_module.release_at)
        copied_lessons = Lesson.objects.filter(topic__module__course=copied).order_by(
            "order"
        )
        copied_first, copied_second = copied_lessons
        self.assertNotEqual(copied_first.pk, first_lesson.pk)
        self.assertNotEqual(copied_second.pk, second_lesson.pk)
        self.assertFalse(copied_first.is_published)
        self.assertFalse(copied_second.is_published)
        self.assertEqual(copied_second.required_lesson, copied_first)
        copied_material = copied_first.materials.get()
        self.assertEqual(copied_material.original_filename, "handbook.pdf")
        self.assertEqual(
            copied_material.file.name,
            "learning/materials/handbook.pdf",
        )
        self.assertEqual(copied_material.created_by, self.user)
        self.assertFalse(copied.teaching_assignments.exists())
        self.assertFalse(copied.scorm_packages.exists())

    def test_copy_requires_authentication_and_copy_permission(self):
        anonymous_response = self.client.post(
            self.copy_url(),
            {"title": "Anonymous Copy", "code": "ANON-COPY"},
            format="json",
        )
        teacher = get_user_model().objects.create_user(username="copy-denied")
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        CourseTeachingAssignment.objects.create(
            course=self.course,
            user=teacher,
            role=CourseTeachingRole.TEACHER,
            is_primary=True,
        )
        self.client.force_authenticate(teacher)

        forbidden_response = self.client.post(
            self.copy_url(),
            {"title": "Teacher Copy", "code": "TEACHER-COPY"},
            format="json",
        )

        self.assertEqual(
            anonymous_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            forbidden_response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_copy_rejects_duplicate_code_with_stable_error(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            self.copy_url(),
            {"title": "Duplicate", "code": self.course.code.lower()},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "course_code_exists")
        self.assertEqual(Course.objects.count(), 1)

    def test_copy_is_atomic_when_nested_content_creation_fails(self):
        self.build_copy_structure()
        initial_course_count = Course.objects.count()

        with patch.object(
            LearningMaterial.objects,
            "create",
            side_effect=RuntimeError("copy failed"),
        ), self.assertRaisesMessage(RuntimeError, "copy failed"):
            copy_course(
                self.course,
                "Rolled Back Copy",
                "ROLLBACK-COPY",
                self.user,
            )

        self.assertEqual(Course.objects.count(), initial_course_count)
        self.assertFalse(Course.objects.filter(code="ROLLBACK-COPY").exists())

    def test_content_manager_creates_source_independent_course_template(self):
        self.build_copy_structure()

        response = self.create_template()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("snapshot", response.data)
        self.assertNotIn("source_course", response.data)
        template = CourseTemplate.objects.get(pk=response.data["id"])
        self.assertEqual(template.created_by, self.user)
        self.assertEqual(template.updated_by, self.user)
        self.assertEqual(template.snapshot["version"], 1)
        self.assertEqual(len(template.snapshot["modules"]), 2)
        lesson_data = template.snapshot["modules"][0]["topics"][0]["lessons"]
        self.assertEqual(
            lesson_data[1]["required_lesson_ref"],
            lesson_data[0]["ref"],
        )
        self.assertNotIn(
            "source_course",
            {field.name for field in CourseTemplate._meta.get_fields()},
        )

    def test_template_can_create_course_after_source_is_deleted(self):
        template_response = self.create_template()
        template = CourseTemplate.objects.get(pk=template_response.data["id"])
        self.course.delete()

        response = self.client.post(
            self.template_create_course_url(template),
            {"title": "Independent course", "code": "INDEPENDENT-1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Course.objects.filter(code="INDEPENDENT-1").exists())

    def test_active_templates_can_be_listed_and_retrieved(self):
        active_response = self.create_template()
        active = CourseTemplate.objects.get(pk=active_response.data["id"])
        inactive_response = self.create_template(
            title="Inactive template",
            is_active=False,
        )
        inactive = CourseTemplate.objects.get(pk=inactive_response.data["id"])

        list_response = self.client.get(self.template_list_url())
        detail_response = self.client.get(self.template_detail_url(active))
        inactive_detail_response = self.client.get(self.template_detail_url(inactive))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in list_response.data], [active.pk])
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["title"], active.title)
        self.assertEqual(
            inactive_detail_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_active_template_creates_full_draft_course(self):
        self.build_copy_structure()
        template_response = self.create_template()
        template = CourseTemplate.objects.get(pk=template_response.data["id"])

        response = self.client.post(
            self.template_create_course_url(template),
            {"title": "From Template", "code": "tmpl-101"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        course = Course.objects.get(pk=response.data["id"])
        self.assertEqual(course.code, "TMPL-101")
        self.assertEqual(course.status, CourseStatus.DRAFT)
        self.assertEqual(course.created_by, self.user)
        self.assertEqual(course.modules.count(), 2)
        lessons = Lesson.objects.filter(topic__module__course=course).order_by("order")
        first_lesson, second_lesson = lessons
        self.assertFalse(first_lesson.is_published)
        self.assertEqual(second_lesson.required_lesson, first_lesson)
        self.assertEqual(first_lesson.materials.get().title, "Handbook")
        self.assertFalse(course.teaching_assignments.exists())
        self.assertFalse(course.scorm_packages.exists())

    def test_template_endpoints_enforce_authentication_and_permissions(self):
        anonymous_response = self.client.get(self.template_list_url())
        teacher = get_user_model().objects.create_user(username="template-denied")
        teacher.roles.add(Role.objects.get(code=RoleCode.TEACHER))
        self.client.force_authenticate(teacher)

        forbidden_response = self.client.get(self.template_list_url())

        self.assertEqual(
            anonymous_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            forbidden_response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_inactive_template_cannot_create_course(self):
        template_response = self.create_template(is_active=False)
        template = CourseTemplate.objects.get(pk=template_response.data["id"])

        response = self.client.post(
            self.template_create_course_url(template),
            {"title": "Inactive", "code": "INACTIVE-1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Course.objects.filter(code="INACTIVE-1").exists())

    def test_create_course_from_template_also_requires_create_permission(self):
        template_response = self.create_template()
        template = CourseTemplate.objects.get(pk=template_response.data["id"])
        content_manager = Role.objects.get(code=RoleCode.CONTENT_MANAGER)
        content_manager.permissions.remove(
            LMSPermission.objects.get(code=LMSPermissionCode.COURSES_CREATE)
        )

        response = self.client.post(
            self.template_create_course_url(template),
            {"title": "Forbidden", "code": "FORBIDDEN-1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Course.objects.filter(code="FORBIDDEN-1").exists())

    def test_invalid_template_snapshot_has_stable_error(self):
        template_response = self.create_template()
        template = CourseTemplate.objects.get(pk=template_response.data["id"])
        template.snapshot = {"version": 999}
        template.save(update_fields=("snapshot", "updated_at"))

        response = self.client.post(
            self.template_create_course_url(template),
            {"title": "Invalid", "code": "INVALID-1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"]["code"],
            "invalid_course_template",
        )
        self.assertFalse(Course.objects.filter(code="INVALID-1").exists())

    def test_template_rejects_duplicate_course_code_with_stable_error(self):
        template_response = self.create_template()
        template = CourseTemplate.objects.get(pk=template_response.data["id"])

        response = self.client.post(
            self.template_create_course_url(template),
            {"title": "Duplicate", "code": self.course.code.lower()},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "course_code_exists")

    def test_routes_have_stable_names(self):
        self.assertEqual(
            reverse("api-v1:courses-v1:list-create"),
            self.list_url,
        )
        self.assertEqual(
            reverse("api-v1:courses-v1:detail", kwargs={"pk": self.course.pk}),
            f"{self.list_url}{self.course.pk}/",
        )
        self.assertEqual(
            self.copy_url(),
            f"{self.list_url}{self.course.pk}/copy/",
        )
        self.assertEqual(self.template_list_url(), "/api/v1/course-templates/")
