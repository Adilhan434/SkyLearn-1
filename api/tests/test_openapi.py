from drf_spectacular.generators import SchemaGenerator
from rest_framework import status
from rest_framework.test import APITestCase


class OpenApiTests(APITestCase):
    expected_paths = {
        "/api/v1/",
        "/api/v1/health/",
        "/api/v1/auth/login/",
        "/api/v1/auth/logout/",
        "/api/v1/auth/refresh/",
        "/api/v1/auth/me/",
        "/api/v1/users/",
        "/api/v1/users/{id}/",
        "/api/v1/roles/",
        "/api/v1/courses/",
        "/api/v1/courses/{id}/",
        "/api/v1/courses/{id}/history/",
        "/api/v1/courses/{id}/readiness/",
        "/api/v1/courses/{id}/structure/",
        "/api/v1/courses/{id}/materials/",
        "/api/v1/courses/{id}/structure/reorder/",
        "/api/v1/courses/{id}/submit-review/",
        "/api/v1/courses/{id}/return-for-revision/",
        "/api/v1/courses/{id}/publish/",
        "/api/v1/courses/{id}/archive/",
        "/api/v1/courses/{id}/restore/",
        "/api/v1/courses/{id}/copy/",
        "/api/v1/courses/{course_pk}/enrollments/",
        "/api/v1/courses/{course_pk}/modules/",
        "/api/v1/modules/{id}/",
        "/api/v1/modules/{module_pk}/topics/",
        "/api/v1/topics/{id}/",
        "/api/v1/topics/{topic_pk}/lessons/",
        "/api/v1/lessons/{id}/",
        "/api/v1/lessons/{lesson_pk}/materials/",
        "/api/v1/lessons/{lesson_pk}/scorm-packages/",
        "/api/v1/materials/{id}/",
        "/api/v1/materials/{id}/download/",
        "/api/v1/materials/{id}/playback/",
        "/api/v1/scorm-packages/{id}/",
        "/api/v1/scorm-packages/{id}/content/{path}",
        "/api/v1/course-templates/",
        "/api/v1/course-templates/{id}/",
        "/api/v1/course-templates/{id}/create-course/",
        "/api/v1/student/courses/",
        "/api/v1/student/courses/{id}/",
        "/api/v1/student/dashboard/",
        "/api/v1/student/progress/",
        "/api/v1/student/courses/{id}/progress/",
        "/api/v1/student/lessons/{id}/start/",
        "/api/v1/student/lessons/{id}/complete/",
        "/api/v1/student/calendar/",
        "/api/v1/calendar/events/",
        "/api/v1/calendar/events/{id}/",
        "/api/v1/integrations/sis/enrollments/sync/",
    }
    public_operations = {
        ("/api/v1/", "get"),
        ("/api/v1/health/", "get"),
        ("/api/v1/auth/login/", "post"),
        ("/api/v1/auth/logout/", "post"),
        ("/api/v1/auth/refresh/", "post"),
    }

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.schema = SchemaGenerator().get_schema(request=None, public=True)

    def iter_operations(self):
        for path, path_item in self.schema["paths"].items():
            for method, operation in path_item.items():
                if method in {"get", "post", "put", "patch", "delete"}:
                    yield path, method, operation

    def test_schema_and_swagger_routes_are_available(self):
        schema_response = self.client.get("/api/schema/")
        docs_response = self.client.get("/api/docs/")

        self.assertEqual(schema_response.status_code, status.HTTP_200_OK)
        self.assertEqual(docs_response.status_code, status.HTTP_200_OK)

    def test_schema_contains_all_release1_endpoints(self):
        self.assertSetEqual(set(self.schema["paths"]), self.expected_paths)

    def test_schema_defines_cookie_authentication(self):
        self.assertEqual(
            self.schema["components"]["securitySchemes"]["cookieAuth"],
            {
                "type": "apiKey",
                "in": "cookie",
                "name": "access_token",
                "description": ("JWT access token stored in an httpOnly cookie."),
            },
        )

    def test_operations_document_permissions_and_security(self):
        for path, method, operation in self.iter_operations():
            with self.subTest(path=path, method=method):
                self.assertIn("**Permissions:**", operation["description"])
                if (path, method) in self.public_operations:
                    self.assertEqual(operation["security"], [])
                else:
                    self.assertTrue(operation["security"])
                    self.assertIn("401", operation["responses"])
                    self.assertIn("403", operation["responses"])

    def test_schema_documents_common_and_domain_errors(self):
        components = self.schema["components"]
        self.assertIn("APIError", components["schemas"])
        self.assertSetEqual(
            set(components["responses"]),
            {
                "ValidationError",
                "AuthenticationError",
                "PermissionDeniedError",
                "NotFoundError",
                "ConflictError",
                "InternalServerError",
            },
        )

        publish = self.schema["paths"]["/api/v1/courses/{id}/publish/"]["post"]
        self.assertIn("invalid_course_transition", publish["description"])
        self.assertIn("400", publish["responses"])
        download = self.schema["paths"]["/api/v1/materials/{id}/download/"]["get"]
        self.assertIn("material_download_not_allowed", download["description"])
        self.assertIn("400", download["responses"])
        self.assertIn("404", download["responses"])

        lesson = self.schema["paths"]["/api/v1/lessons/{id}/"]["delete"]
        self.assertIn("lesson_is_required", lesson["description"])
        self.assertIn("409", lesson["responses"])

    def test_schema_documents_filters_and_pagination(self):
        expected_parameters = {
            "/api/v1/courses/": {
                "created_by",
                "department",
                "faculty",
                "language",
                "ordering",
                "page",
                "page_size",
                "program",
                "search",
                "semester",
                "status",
                "teacher",
            },
            "/api/v1/courses/{id}/materials/": {
                "id",
                "lesson",
                "module",
                "search",
                "type",
            },
            "/api/v1/users/": {
                "is_active",
                "page",
                "page_size",
                "role",
                "search",
            },
            "/api/v1/student/calendar/": {
                "course",
                "date_from",
                "date_to",
                "event_type",
                "page",
                "page_size",
            },
        }
        for path, expected in expected_parameters.items():
            with self.subTest(path=path):
                actual = {
                    parameter["name"]
                    for parameter in self.schema["paths"][path]["get"]["parameters"]
                }
                self.assertSetEqual(actual, expected)

    def test_upload_requests_use_binary_multipart_schemas(self):
        uploads = {
            "/api/v1/lessons/{lesson_pk}/materials/": (
                "LearningMaterialRequest",
                "file",
            ),
            "/api/v1/lessons/{lesson_pk}/scorm-packages/": (
                "ScormPackageRequest",
                "file",
            ),
            "/api/v1/courses/": ("CourseWriteRequest", "cover"),
        }
        for path, (component_name, file_field) in uploads.items():
            with self.subTest(path=path):
                request = self.schema["paths"][path]["post"]["requestBody"]
                self.assertIn("multipart/form-data", request["content"])
                component = self.schema["components"]["schemas"][component_name]
                self.assertEqual(
                    component["properties"][file_field]["format"],
                    "binary",
                )
                self.assertTrue(request["content"]["multipart/form-data"]["examples"])

    def test_schema_contains_explicit_request_and_response_examples(self):
        login = self.schema["paths"]["/api/v1/auth/login/"]["post"]
        self.assertTrue(login["requestBody"]["content"]["application/json"]["examples"])
        self.assertTrue(
            login["responses"]["200"]["content"]["application/json"]["examples"]
        )

        course_list = self.schema["paths"]["/api/v1/courses/"]["get"]
        self.assertTrue(
            course_list["responses"]["200"]["content"]["application/json"]["examples"]
        )
        health = self.schema["paths"]["/api/v1/health/"]["get"]
        self.assertTrue(
            health["responses"]["200"]["content"]["application/json"]["examples"]
        )
