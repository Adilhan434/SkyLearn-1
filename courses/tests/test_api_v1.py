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

    def test_routes_have_stable_names(self):
        self.assertEqual(
            reverse("api-v1:courses-v1:list-create"),
            self.list_url,
        )
        self.assertEqual(
            reverse("api-v1:courses-v1:detail", kwargs={"pk": self.course.pk}),
            f"{self.list_url}{self.course.pk}/",
        )
