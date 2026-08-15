from io import StringIO

from django.core.management import call_command
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from audit.models import CourseHistoryAction, CourseHistoryEvent
from courses.models import CourseStatus
from organization.models import Program, Semester


class Release1AcceptanceTests(APITestCase):
    demo_password = "Demo123!"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        call_command(
            "seed_release1",
            password=cls.demo_password,
            allow_production=True,
            stdout=StringIO(),
        )

    def test_teacher_can_complete_course_authoring_and_submit_review_flow(self):
        login = self.client.post(
            reverse("api-v1:auth:login"),
            {
                "login": "teacher@su.edu.kg",
                "password": self.demo_password,
            },
            format="json",
        )

        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", self.client.cookies)
        self.assertIn("refresh_token", self.client.cookies)

        current_user = self.client.get(reverse("api-v1:auth:me"))
        self.assertEqual(current_user.status_code, status.HTTP_200_OK)
        self.assertEqual(current_user.data["roles"], ["teacher"])
        self.assertIn("courses.create", current_user.data["permissions"])
        self.assertIn("courses.submit_review", current_user.data["permissions"])

        courses_url = reverse("api-v1:courses-v1:list-create")
        teacher_courses = self.client.get(courses_url)
        self.assertEqual(teacher_courses.status_code, status.HTTP_200_OK)

        program = Program.objects.select_related("department__faculty").get(code="SE")
        semester = Semester.objects.get(name="Fall 2026")
        create_course = self.client.post(
            courses_url,
            {
                "title": "Teacher Acceptance Course",
                "code": "E2E-TCH-101",
                "description": "Initial acceptance description",
                "language": "en",
                "credits": 5,
                "semester": semester.pk,
                "faculty": program.department.faculty_id,
                "department": program.department_id,
                "program": program.pk,
                "start_date": "2026-09-01",
                "end_date": "2026-12-20",
            },
            format="json",
        )
        self.assertEqual(create_course.status_code, status.HTTP_201_CREATED)
        course_id = create_course.data["id"]

        update_course = self.client.patch(
            reverse("api-v1:courses-v1:detail", kwargs={"pk": course_id}),
            {"description": "Updated entirely through the Teacher API."},
            format="json",
        )
        self.assertEqual(update_course.status_code, status.HTTP_200_OK)

        create_module = self.client.post(
            reverse(
                "api-v1:courses-v1:module-create",
                kwargs={"course_pk": course_id},
            ),
            {"title": "Acceptance Module"},
            format="json",
        )
        self.assertEqual(create_module.status_code, status.HTTP_201_CREATED)

        create_topic = self.client.post(
            reverse(
                "api-v1:learning-v1:topic-create",
                kwargs={"module_pk": create_module.data["id"]},
            ),
            {"title": "Acceptance Topic"},
            format="json",
        )
        self.assertEqual(create_topic.status_code, status.HTTP_201_CREATED)

        create_lesson = self.client.post(
            reverse(
                "api-v1:learning-v1:lesson-create",
                kwargs={"topic_pk": create_topic.data["id"]},
            ),
            {
                "title": "Acceptance Lesson",
                "lesson_type": "text",
                "content": "Teacher-authored lesson content.",
                "is_published": True,
            },
            format="json",
        )
        self.assertEqual(create_lesson.status_code, status.HTTP_201_CREATED)

        create_material = self.client.post(
            reverse(
                "api-v1:learning-v1:lesson-material-list-create",
                kwargs={"lesson_pk": create_lesson.data["id"]},
            ),
            {
                "title": "Acceptance Reference",
                "type": "external_link",
                "external_url": "https://example.edu/teacher-reference",
            },
            format="json",
        )
        self.assertEqual(create_material.status_code, status.HTTP_201_CREATED)

        readiness = self.client.get(
            reverse(
                "api-v1:courses-v1:readiness",
                kwargs={"pk": course_id},
            )
        )
        self.assertEqual(readiness.status_code, status.HTTP_200_OK)
        self.assertTrue(readiness.data["ready_for_review"])

        submit_review = self.client.post(
            reverse(
                "api-v1:courses-v1:submit-review",
                kwargs={"pk": course_id},
            )
        )
        self.assertEqual(submit_review.status_code, status.HTTP_200_OK)
        self.assertEqual(submit_review.data["status"], CourseStatus.UNDER_REVIEW)
        self.assertTrue(
            CourseHistoryEvent.objects.filter(
                course_id=course_id,
                action=CourseHistoryAction.SUBMITTED_FOR_REVIEW,
            ).exists()
        )

    def test_content_manager_can_return_course_for_revision(self):
        manager_login = self.client.post(
            reverse("api-v1:auth:login"),
            {
                "login": "content@su.edu.kg",
                "password": self.demo_password,
            },
            format="json",
        )
        self.assertEqual(manager_login.status_code, status.HTTP_200_OK)

        courses_url = reverse("api-v1:courses-v1:list-create")
        under_review_courses = self.client.get(
            courses_url,
            {"status": CourseStatus.UNDER_REVIEW},
        )
        self.assertEqual(under_review_courses.status_code, status.HTTP_200_OK)
        self.assertGreater(under_review_courses.data["count"], 0)
        course_id = under_review_courses.data["results"][0]["id"]

        course_detail_url = reverse(
            "api-v1:courses-v1:detail",
            kwargs={"pk": course_id},
        )
        course_detail = self.client.get(course_detail_url)
        self.assertEqual(course_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(course_detail.data["status"], CourseStatus.UNDER_REVIEW)

        course_structure = self.client.get(
            reverse(
                "api-v1:courses-v1:structure",
                kwargs={"pk": course_id},
            )
        )
        self.assertEqual(course_structure.status_code, status.HTTP_200_OK)

        course_materials = self.client.get(
            reverse(
                "api-v1:courses-v1:material-list",
                kwargs={"pk": course_id},
            )
        )
        self.assertEqual(course_materials.status_code, status.HTTP_200_OK)

        review_comment = "Add learning outcomes and revise the lesson materials."
        return_for_revision = self.client.post(
            reverse(
                "api-v1:courses-v1:return-for-revision",
                kwargs={"pk": course_id},
            ),
            {"comment": review_comment},
            format="json",
        )
        self.assertEqual(return_for_revision.status_code, status.HTTP_200_OK)
        self.assertEqual(
            return_for_revision.data["status"],
            CourseStatus.NEEDS_REVISION,
        )
        self.assertEqual(return_for_revision.data["review_comment"], review_comment)

        self.client.cookies.clear()
        teacher_login = self.client.post(
            reverse("api-v1:auth:login"),
            {
                "login": "teacher@su.edu.kg",
                "password": self.demo_password,
            },
            format="json",
        )
        self.assertEqual(teacher_login.status_code, status.HTTP_200_OK)

        teacher_course_detail = self.client.get(course_detail_url)
        self.assertEqual(teacher_course_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(
            teacher_course_detail.data["status"],
            CourseStatus.NEEDS_REVISION,
        )
        self.assertEqual(
            teacher_course_detail.data["review_comment"],
            review_comment,
        )

    def test_admin_can_publish_copy_archive_and_read_complete_history(self):
        admin_login = self.client.post(
            reverse("api-v1:auth:login"),
            {
                "login": "admin@su.edu.kg",
                "password": self.demo_password,
            },
            format="json",
        )
        self.assertEqual(admin_login.status_code, status.HTTP_200_OK)

        under_review_courses = self.client.get(
            reverse("api-v1:courses-v1:list-create"),
            {"status": CourseStatus.UNDER_REVIEW},
        )
        self.assertEqual(under_review_courses.status_code, status.HTTP_200_OK)
        self.assertGreater(under_review_courses.data["count"], 0)
        course_id = under_review_courses.data["results"][0]["id"]

        course_detail = self.client.get(
            reverse("api-v1:courses-v1:detail", kwargs={"pk": course_id})
        )
        self.assertEqual(course_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(course_detail.data["status"], CourseStatus.UNDER_REVIEW)

        publish = self.client.post(
            reverse("api-v1:courses-v1:publish", kwargs={"pk": course_id})
        )
        self.assertEqual(publish.status_code, status.HTTP_200_OK)
        self.assertEqual(publish.data["status"], CourseStatus.PUBLISHED)

        copy = self.client.post(
            reverse("api-v1:courses-v1:copy", kwargs={"pk": course_id}),
            {
                "title": "Admin Acceptance Copy",
                "code": "E2E-ADM-COPY-101",
            },
            format="json",
        )
        self.assertEqual(copy.status_code, status.HTTP_201_CREATED)
        self.assertEqual(copy.data["status"], CourseStatus.DRAFT)

        archive = self.client.post(
            reverse("api-v1:courses-v1:archive", kwargs={"pk": course_id})
        )
        self.assertEqual(archive.status_code, status.HTTP_200_OK)
        self.assertEqual(archive.data["status"], CourseStatus.ARCHIVED)

        history = self.client.get(
            reverse("api-v1:courses-v1:history", kwargs={"pk": course_id})
        )
        self.assertEqual(history.status_code, status.HTTP_200_OK)
        history_actions = {event["action"] for event in history.data["results"]}
        self.assertTrue(
            {
                CourseHistoryAction.PUBLISHED,
                CourseHistoryAction.COPIED,
                CourseHistoryAction.ARCHIVED,
            }.issubset(history_actions)
        )
