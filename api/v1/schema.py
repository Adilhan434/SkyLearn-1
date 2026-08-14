def include_only_v1_endpoints(endpoints):
    """Keep legacy routes working without including them in Release 1 docs."""

    return [endpoint for endpoint in endpoints if endpoint[0].startswith("/api/v1/")]


PUBLIC_OPERATIONS = {
    ("/api/v1/", "get"),
    ("/api/v1/health/", "get"),
    ("/api/v1/auth/login/", "post"),
    ("/api/v1/auth/logout/", "post"),
    ("/api/v1/auth/refresh/", "post"),
}

REQUEST_EXAMPLES = {
    ("/api/v1/auth/login/", "post"): {
        "login": "teacher@su.edu.kg",
        "password": "Demo123!",
    },
    ("/api/v1/courses/", "post"): {
        "title": "Introduction to Programming",
        "code": "CS101",
        "description": "Programming foundations",
        "language": "en",
        "credits": 5,
        "semester": 1,
        "teacher": 5,
        "faculty": 1,
        "department": 1,
        "program": 1,
        "start_date": "2026-09-01",
        "end_date": "2026-12-20",
    },
    ("/api/v1/courses/{id}/copy/", "post"): {
        "title": "Introduction to Programming - Copy",
        "code": "CS101-2027",
    },
    ("/api/v1/courses/{id}/return-for-revision/", "post"): {
        "comment": "Add materials to lesson 2."
    },
    ("/api/v1/courses/{id}/structure/reorder/", "post"): {
        "type": "lesson",
        "items": [{"id": 12, "order": 1}, {"id": 15, "order": 2}],
    },
    ("/api/v1/courses/{course_pk}/enrollments/", "post"): {
        "student": 20,
        "source": "manual",
        "external_sis_id": "",
    },
    ("/api/v1/calendar/events/", "post"): {
        "course": 1,
        "title": "Module released",
        "event_type": "module_release",
        "start_at": "2026-09-10T09:00:00+06:00",
        "end_at": None,
        "is_public": True,
    },
    ("/api/v1/integrations/sis/enrollments/sync/", "post"): {
        "external_event_id": "sis-event-1001",
        "student_external_id": "SU-2024-0012",
        "course_code": "CS101",
        "action": "enroll",
    },
    ("/api/v1/lessons/{lesson_pk}/materials/", "post"): {
        "title": "Lecture slides",
        "description": "Slides for the introductory lesson.",
        "type": "pdf",
        "file": "<binary>",
        "download_allowed": True,
    },
    ("/api/v1/lessons/{lesson_pk}/scorm-packages/", "post"): {
        "title": "Interactive introduction",
        "file": "<binary ZIP containing imsmanifest.xml>",
    },
}

RESPONSE_EXAMPLES = {
    ("/api/v1/health/", "get", "200"): {
        "status": "ok",
        "database": "ok",
        "service": "su-lms-backend",
    },
    ("/api/v1/auth/login/", "post", "200"): {
        "user": {
            "id": 5,
            "email": "teacher@su.edu.kg",
            "full_name": "Teacher Demo",
            "roles": ["teacher"],
        }
    },
    ("/api/v1/courses/", "get", "200"): {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": 1,
                "title": "Introduction to Programming",
                "code": "CS101",
                "status": "draft",
                "credits": 5,
            }
        ],
    },
    ("/api/v1/courses/", "post", "201"): {
        "id": 1,
        "title": "Introduction to Programming",
        "code": "CS101",
        "status": "draft",
        "credits": 5,
    },
    ("/api/v1/courses/{id}/readiness/", "get", "200"): {
        "score": 82,
        "ready_for_review": False,
        "checks": [
            {"key": "metadata", "status": "complete"},
            {"key": "lesson_materials", "status": "warning"},
        ],
    },
    ("/api/v1/student/courses/{id}/progress/", "get", "200"): {
        "course_id": 1,
        "total_lessons": 10,
        "completed_lessons": 4,
        "progress_percent": 40,
    },
    ("/api/v1/lessons/{lesson_pk}/materials/", "post", "201"): {
        "id": 10,
        "title": "Lecture slides",
        "type": "pdf",
        "original_filename": "lecture-slides.pdf",
        "download_allowed": True,
        "download_url": "/api/v1/materials/10/download/",
    },
    ("/api/v1/lessons/{lesson_pk}/scorm-packages/", "post", "201"): {
        "id": 4,
        "title": "Interactive introduction",
        "version": "1.2",
        "launch_path": "index.html",
        "status": "ready",
        "launch_url": "/api/v1/scorm-packages/4/content/index.html",
    },
}

DOMAIN_ERROR_CODES = {
    "/copy/": ("course_code_exists",),
    "/create-course/": ("course_code_exists", "invalid_course_template"),
    "/submit-review/": ("course_not_ready", "invalid_course_transition"),
    "/return-for-revision/": ("invalid_course_transition",),
    "/publish/": ("invalid_course_transition",),
    "/archive/": ("invalid_course_transition",),
    "/restore/": ("invalid_course_transition",),
    "/structure/reorder/": ("invalid_structure_order",),
    "/api/v1/modules/{id}/": ("structure_not_empty",),
    "/api/v1/topics/{id}/": ("structure_not_empty",),
    "/api/v1/lessons/{id}/": ("lesson_is_required",),
    "/download/": (
        "material_download_not_allowed",
        "material_file_unavailable",
    ),
    "/playback/": ("video_not_ready", "material_file_unavailable"),
    "/scorm-packages/{id}/content/": ("scorm_content_unavailable",),
    "/api/v1/courses/{course_pk}/enrollments/": ("already_enrolled",),
    "/api/v1/student/courses/{id}": ("student_course_not_found",),
    "/student/lessons/": ("lesson_locked", "student_lesson_not_found"),
    "/integrations/sis/": (
        "sis_event_conflict",
        "sis_student_not_found",
        "sis_course_not_found",
        "enrollment_not_found",
    ),
}

CONFLICT_ERROR_CODES = {
    "lesson_is_required",
    "lesson_locked",
    "sis_event_conflict",
    "structure_not_empty",
    "video_not_ready",
}

NOT_FOUND_ERROR_CODES = {
    "enrollment_not_found",
    "sis_course_not_found",
    "sis_student_not_found",
    "student_course_not_found",
    "student_lesson_not_found",
}


def _permission_text(path, method):
    if (path, method) in PUBLIC_OPERATIONS:
        return "Public endpoint. No authentication required."
    if path.startswith("/api/v1/users/") or path == "/api/v1/roles/":
        return "LMS Admin or Super Admin role."
    if path.startswith("/api/v1/student/"):
        return "Student role, active account and resource-specific enrollment access."
    if path.startswith("/api/v1/integrations/sis/"):
        return "Authenticated user with `enrollments.manage`."
    if path.startswith("/api/v1/calendar/"):
        permission = "calendar.view" if method == "get" else "calendar.manage"
        return f"Authenticated user with `{permission}` and course access."
    if path.startswith("/api/v1/course-templates/"):
        if path.endswith("/create-course/"):
            return "Authenticated user with `courses.copy` and `courses.create`."
        return "Authenticated user with `courses.copy`; source access is required."
    if path.startswith("/api/v1/courses/"):
        if path.endswith("/enrollments/"):
            permission = "enrollments.view" if method == "get" else "enrollments.manage"
        elif path.endswith("/modules/") or path.endswith("/structure/reorder/"):
            permission = "course_structure.manage"
        elif path.endswith("/copy/"):
            permission = "courses.copy"
        elif path.endswith("/submit-review/"):
            permission = "courses.submit_review"
        elif path.endswith("/return-for-revision/"):
            permission = "courses.review"
        elif path.endswith("/publish/"):
            permission = "courses.publish"
        elif path.endswith("/archive/") or path.endswith("/restore/"):
            permission = "courses.archive"
        elif path.endswith("/materials/"):
            permission = "materials.view"
        elif method == "post":
            permission = "courses.create"
        elif method == "patch":
            permission = "courses.edit"
        elif method == "delete":
            permission = "courses.delete"
        else:
            permission = "courses.view"
        return f"Authenticated user with `{permission}` and object access."
    if "/materials" in path or path.startswith("/api/v1/scorm-packages/"):
        if method == "post":
            permission = "materials.upload"
        elif method in {"put", "patch"}:
            permission = "materials.edit"
        elif method == "delete":
            permission = "materials.delete"
        else:
            permission = "materials.view"
        return f"Authenticated user with `{permission}` and course access."
    if any(part in path for part in ("/modules/", "/topics/", "/lessons/")):
        return "Authenticated user with `course_structure.manage` and course access."
    return "Authenticated user with resource-specific object access."


def _error_response(description, code, message, fields=None):
    return {
        "description": description,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/APIError"},
                "examples": {
                    code: {
                        "summary": description,
                        "value": {
                            "error": {
                                "code": code,
                                "message": message,
                                "fields": fields or {},
                            }
                        },
                    }
                },
            }
        },
    }


def _register_error_components(result):
    components = result.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    schemas["APIError"] = {
        "type": "object",
        "required": ["error"],
        "properties": {
            "error": {
                "type": "object",
                "required": ["code", "message", "fields"],
                "properties": {
                    "code": {"type": "string"},
                    "message": {"type": "string"},
                    "fields": {"type": "object", "additionalProperties": True},
                    "details": {"type": "object", "additionalProperties": True},
                },
            }
        },
    }
    responses = components.setdefault("responses", {})
    responses.update(
        {
            "ValidationError": _error_response(
                "Request validation failed.",
                "validation_error",
                "Validation failed.",
                {"field": ["This field is required."]},
            ),
            "AuthenticationError": _error_response(
                "Authentication is missing, invalid or expired.",
                "authentication_failed",
                "Authentication failed.",
            ),
            "PermissionDeniedError": _error_response(
                "The authenticated user lacks permission.",
                "permission_denied",
                "Permission denied.",
            ),
            "NotFoundError": _error_response(
                "The resource is missing or outside the user's object scope.",
                "not_found",
                "Resource not found.",
            ),
            "ConflictError": _error_response(
                "The request conflicts with current domain state.",
                "invalid_course_transition",
                "The requested state transition is not allowed.",
            ),
            "InternalServerError": _error_response(
                "Unexpected server error without sensitive internal details.",
                "internal_server_error",
                "An internal server error occurred.",
            ),
        }
    )


def _add_explicit_examples(path, method, operation):
    request_example = REQUEST_EXAMPLES.get((path, method))
    if request_example is not None:
        for media in operation.get("requestBody", {}).get("content", {}).values():
            media.setdefault("examples", {})["requestExample"] = {
                "summary": "Example request",
                "value": request_example,
            }

    for (example_path, example_method, status), value in RESPONSE_EXAMPLES.items():
        if (path, method) != (example_path, example_method):
            continue
        response = operation.get("responses", {}).get(status, {})
        for media in response.get("content", {}).values():
            media.setdefault("examples", {})["responseExample"] = {
                "summary": "Example response",
                "value": value,
            }


def enrich_openapi_schema(result, generator, request, public):
    """Add shared permissions, errors and examples to Release 1 operations."""

    del generator, request, public
    _register_error_components(result)
    for path, path_item in result.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            is_public = (path, method) in PUBLIC_OPERATIONS
            operation["security"] = [] if is_public else operation.get("security", [])
            permission = _permission_text(path, method)
            description = operation.get("description", "").strip()
            operation[
                "description"
            ] = f"{description}\n\n**Permissions:** {permission}".strip()

            responses = operation.setdefault("responses", {})
            if method in {"post", "put", "patch"} or operation.get("parameters"):
                responses.setdefault(
                    "400", {"$ref": "#/components/responses/ValidationError"}
                )
            if not is_public:
                responses.setdefault(
                    "401", {"$ref": "#/components/responses/AuthenticationError"}
                )
                responses.setdefault(
                    "403", {"$ref": "#/components/responses/PermissionDeniedError"}
                )
            elif path.startswith("/api/v1/auth/"):
                responses.setdefault(
                    "401", {"$ref": "#/components/responses/AuthenticationError"}
                )
            if "{" in path:
                responses.setdefault(
                    "404", {"$ref": "#/components/responses/NotFoundError"}
                )
            domain_codes = sorted(
                {
                    code
                    for marker, codes in DOMAIN_ERROR_CODES.items()
                    if marker in path
                    for code in codes
                }
            )
            if domain_codes:
                operation["description"] += "\n\n**Domain error codes:** " + ", ".join(
                    f"`{code}`" for code in domain_codes
                )
                if set(domain_codes) & CONFLICT_ERROR_CODES:
                    responses.setdefault(
                        "409", {"$ref": "#/components/responses/ConflictError"}
                    )
                if set(domain_codes) & NOT_FOUND_ERROR_CODES:
                    responses.setdefault(
                        "404", {"$ref": "#/components/responses/NotFoundError"}
                    )
                if set(domain_codes) - CONFLICT_ERROR_CODES - NOT_FOUND_ERROR_CODES:
                    responses.setdefault(
                        "400", {"$ref": "#/components/responses/ValidationError"}
                    )
            responses.setdefault(
                "500", {"$ref": "#/components/responses/InternalServerError"}
            )
            _add_explicit_examples(path, method, operation)
    return result
