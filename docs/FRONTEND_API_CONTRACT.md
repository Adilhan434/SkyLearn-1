# SU-LMS Release 1 frontend API contract

## 1. Scope and conventions

This document maps the Release 1 frontend screens to the implemented backend
contract. All new LMS endpoints use the `/api/v1/` namespace. Legacy endpoints
outside that namespace are not part of this contract.

The examples show stable fields used by the frontend; OpenAPI remains the
machine-readable source for complete field types.

### Authentication

The browser flow uses `HttpOnly` `access_token` and `refresh_token` cookies.
Every frontend request must set credentials:

```js
fetch(url, {
  credentials: "include",
  headers: { "Content-Type": "application/json" },
});
```

Bearer access tokens are accepted as a compatibility fallback. The frontend
must never read or persist the HttpOnly cookie values. For deployments that
enable CSRF token enforcement, state-changing requests must also send the
configured `X-CSRFToken` header.

### Pagination

Paginated endpoints accept `page` and `page_size` and return:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": []
}
```

Unless stated otherwise, the page size is 20 and the maximum requested page
size is 100. The staff enrollment list uses 50 by default and allows up to 200.

### Error response

The frontend must branch on `error.code`, never on human-readable text:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Validation failed.",
    "fields": {
      "code": ["A course with this code already exists."]
    }
  }
}
```

Common codes are `validation_error`, `authentication_required`,
`authentication_failed`,
`permission_denied`, `not_found`, `method_not_allowed` and
`internal_server_error`. Domain-specific codes are documented with the
corresponding screen.

`authentication_required` means credentials were not supplied.
`authentication_failed` means supplied login data or a token is invalid or
expired. Frontend logic must branch on `error.code`, never on localized
`error.message`.

## 2. Screen-to-endpoint matrix

| Screen | Method and endpoint | Auth / permission | Query or request | Response / errors |
|---|---|---|---|---|
| Login | `POST /api/v1/auth/login/` | Public | `{login, password}`; `login` accepts username, email or student ID-style username | User summary and auth cookies; `authentication_failed`, `validation_error` |
| Current User | `GET /api/v1/auth/me/` | Authenticated | None | User, roles, effective permissions and optional student profile; `authentication_required`, `authentication_failed` |
| Teacher Dashboard | `GET /api/v1/courses/` | `courses.view`, assigned-course scope | Course filters and pagination | Assigned courses. No dedicated teacher aggregate endpoint in Release 1 |
| Admin Dashboard | `GET /api/v1/courses/` plus `GET /api/v1/calendar/events/` | Global course scope and relevant permissions | Filters and pagination | Course/calendar operational data. No dedicated admin metrics endpoint in Release 1 |
| Courses | `GET /api/v1/courses/` | `courses.view` | See Course filters | Paginated compact courses; `permission_denied` |
| Create Course | `POST /api/v1/courses/` | `courses.create` | Course write payload | New Draft course; duplicate codes and invalid fields use `validation_error` |
| Edit Course | `PATCH /api/v1/courses/{id}/` | `courses.edit` plus object scope | Partial Course write payload | Updated course; `not_found`, `permission_denied`, `validation_error` |
| Course Detail | `GET /api/v1/courses/{id}/` | `courses.view` plus object scope | None | Full metadata and lifecycle state; `not_found` |
| Course Builder | `GET /api/v1/courses/{id}/structure/` | `courses.view` plus object scope | None | Nested Module -> Topic -> Lesson tree |
| Module | `POST /api/v1/courses/{id}/modules/`; `PATCH/DELETE /api/v1/modules/{id}/` | `course_structure.manage` plus object scope | Module payload; delete may require `{confirm:true}` | Module data; `invalid_release_condition`, `invalid_structure_order`, `structure_not_empty` |
| Topic | `POST /api/v1/modules/{id}/topics/`; `PATCH/DELETE /api/v1/topics/{id}/` | `course_structure.manage` plus object scope | Topic payload; delete may require `{confirm:true}` | Topic data; `invalid_structure_order`, `structure_not_empty` |
| Lesson | `POST /api/v1/topics/{id}/lessons/`; `GET/PATCH/DELETE /api/v1/lessons/{id}/` | Structure permission plus object scope | Lesson payload | Lesson data; `invalid_release_condition`, `lesson_is_required` |
| Materials | `GET/POST /api/v1/lessons/{id}/materials/`; `GET/PATCH/DELETE /api/v1/materials/{id}/` | Method-specific `materials.*` permission plus object scope | JSON for links, multipart for files | Safe material metadata; `invalid_file_type`, `file_too_large`, validation and permission errors |
| Course Preview | `GET /api/v1/courses/{id}/`; `GET /api/v1/courses/{id}/structure/`; `GET /api/v1/courses/{id}/materials/` | Course/material view permission and object scope | Material filters when required | Composed preview. There is no separate preview endpoint |
| Course Readiness | `GET /api/v1/courses/{id}/readiness/` | `courses.view` plus object scope | None | Score, readiness flag and checks; `not_found` |
| Review | `POST /api/v1/courses/{id}/submit-review/`; `POST /api/v1/courses/{id}/return-for-revision/` | `courses.submit_review` or `courses.review` | Return requires `{comment}` | Updated course; `course_not_ready`, `invalid_course_transition`, `validation_error` |
| Publish | `POST /api/v1/courses/{id}/publish/` | `courses.publish` plus object scope | Empty body | Published course; `invalid_course_transition`, `permission_denied` |
| Archive | `POST /api/v1/courses/{id}/archive/`; `POST /api/v1/courses/{id}/restore/` | `courses.archive` plus object scope | Empty body | Updated course; `invalid_course_transition` |
| Course History | `GET /api/v1/courses/{id}/history/` | `courses.view` plus object scope | `page`, `page_size` | Paginated actor/object events; foreign courses return `not_found` |
| Templates | `GET/POST /api/v1/course-templates/`; `GET /api/v1/course-templates/{id}/` | `courses.copy`; source course scope on create | Template payload | Active templates; `not_found`, `permission_denied` |
| Template -> Course | `POST /api/v1/course-templates/{id}/create-course/` | `courses.copy` and `courses.create` | `{title, code}` | New Draft course; `course_code_exists`, `invalid_course_template` |
| Course Copy | `POST /api/v1/courses/{id}/copy/` | `courses.copy` plus source-course scope | `{title, code}` | New Draft with copied structure/material references; `course_code_exists` |
| Enrollment Management | `GET/POST /api/v1/courses/{id}/enrollments/` | `enrollments.view` or `enrollments.manage` plus course scope | Enrollment payload; pagination defaults to 50, maximum 200 | Enrollment; `already_enrolled`, validation and permission errors |
| Student Dashboard | `GET /api/v1/student/dashboard/` | Student role, active account, `courses.view` | None | Summary, per-course progress, continue-learning target and upcoming events |
| Student Courses | `GET /api/v1/student/courses/` | Student role and `courses.view` | `page`, `page_size` | Active enrolled Published courses |
| Student Course | `GET /api/v1/student/courses/{id}/` | Active enrollment | None | Safe metadata, progress and nested available/locked structure; inaccessible course returns `not_found` |
| Student Lesson | Course detail plus `POST /api/v1/student/lessons/{id}/start/` and `/complete/` | Active enrollment and available lesson | Empty body | Lesson progress; `lesson_locked`, `student_lesson_not_found` |
| Student Materials | Material metadata in Student Course; `GET /api/v1/materials/{id}/download/` or `/playback/` | Active enrollment, published course and available lesson | None | Binary response; `material_download_not_allowed`, `material_file_unavailable`, `video_not_ready` |
| Student Progress | `GET /api/v1/student/progress/`; `GET /api/v1/student/courses/{id}/progress/` | Student role and active enrollment | None | Overall or course progress |
| Student Calendar | `GET /api/v1/student/calendar/` | Student role and `calendar.view` | `date_from`, `date_to`, `course`, `event_type`, pagination | Public events from active Published enrolled courses |
| Staff Calendar | `GET/POST /api/v1/calendar/events/`; `GET/PATCH/DELETE /api/v1/calendar/events/{id}/` | `calendar.view` or `calendar.manage` plus course scope | Calendar filters/event payload | Paginated events or event detail |

## 3. Authentication contract

### Login

```http
POST /api/v1/auth/login/
Content-Type: application/json
```

```json
{
  "login": "teacher@su.edu.kg",
  "password": "Demo123!"
}
```

```json
{
  "user": {
    "id": 5,
    "email": "teacher@su.edu.kg",
    "full_name": "Teacher Demo",
    "roles": ["teacher"]
  }
}
```

The response sets access and refresh cookies. Login failures always use the
same `authentication_failed` response and do not disclose whether an account
exists.

### Refresh, logout and current user

| Method | Endpoint | Body | Success |
|---|---|---|---|
| `POST` | `/api/v1/auth/refresh/` | Empty; refresh cookie is used | `{"message":"Token refreshed successfully."}` and rotated cookies |
| `POST` | `/api/v1/auth/logout/` | Empty | Cookies cleared and `{"message":"Logged out successfully."}` |
| `GET` | `/api/v1/auth/me/` | None | Current user contract below |

```json
{
  "id": 5,
  "email": "teacher@su.edu.kg",
  "first_name": "Teacher",
  "last_name": "Demo",
  "full_name": "Teacher Demo",
  "is_active": true,
  "roles": ["teacher"],
  "permissions": ["course_structure.manage", "courses.edit", "courses.view"],
  "profile": null
}
```

Frontend authorization must use `permissions`; role names are useful for
navigation only.

## 4. Course management contract

### List filters

`GET /api/v1/courses/` supports:

- `search`: title, code, description or assigned teacher full name;
- `status`: `draft`, `under_review`, `needs_revision`, `published`, `archived`;
- `semester`, `faculty`, `department`, `program`, `teacher`, `created_by`: IDs;
- `language`: `en`, `ky`, `ru`;
- `ordering`: `title`, `code`, `created_at`, `updated_at`, `start_date`,
  `end_date`, `status`; prefix with `-` for descending;
- `page`, `page_size`.

List items deliberately omit the nested course structure:

```json
{
  "id": 10,
  "title": "Introduction to Programming",
  "code": "CS101",
  "status": "draft",
  "language": "en",
  "credits": 5,
  "semester": {"id": 1, "name": "Fall 2026"},
  "teacher": {"id": 5, "full_name": "Teacher Demo"},
  "faculty": {"id": 1, "name": "Engineering", "code": "ENG"},
  "department": {"id": 1, "name": "Computer Science", "code": "CS"},
  "program": {"id": 1, "name": "Software Engineering", "code": "SE"},
  "cover": null,
  "start_date": "2026-09-01",
  "end_date": "2026-12-20",
  "updated_at": "2026-08-14T10:00:00+06:00"
}
```

### Create and edit payload

```json
{
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
  "end_date": "2026-12-20"
}
```

`teacher` is optional. Status is read-only in normal create/PATCH requests and
must be changed through lifecycle actions. Cover and syllabus use multipart
form data when files are supplied. `DELETE /api/v1/courses/{id}/` permanently
deletes Draft courses only; other statuses must use archive.

### Readiness and lifecycle

```json
{
  "score": 82,
  "ready_for_review": false,
  "checks": [
    {"key": "metadata", "status": "complete"},
    {
      "key": "lesson_materials",
      "status": "warning",
      "message": "2 lessons do not contain materials."
    }
  ]
}
```

`submit-review` returns `course_not_ready` with `error.details` when required
metadata or structure is missing. `return-for-revision` requires a non-blank
comment. All invalid status changes return `invalid_course_transition`.

### History

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 100,
      "action": "lesson_created",
      "actor": {"id": 5, "full_name": "Teacher Demo"},
      "object": {"type": "lesson", "id": 15, "title": "Introduction"},
      "created_at": "2026-08-14T11:20:00+06:00"
    }
  ]
}
```

`actor` is `null` if the user was deleted. Internal event details are not part
of the public response.

## 5. Course Builder contract

### Nested structure

```json
{
  "course_id": 1,
  "modules": [
    {
      "id": 10,
      "title": "Module 1",
      "order": 1,
      "topics": [
        {
          "id": 15,
          "title": "Introduction",
          "order": 1,
          "lessons": [
            {
              "id": 20,
              "title": "Lesson 1",
              "order": 1,
              "lesson_type": "video"
            }
          ]
        }
      ]
    }
  ]
}
```

Module write fields are `title`, `description`, optional `order`,
`release_type`, `release_at`. Topic fields are `title`, `description`, optional
`order`. Lesson fields are `title`, `description`, `lesson_type`, `content`,
`estimated_duration_minutes`, optional `order`, `release_type`, `release_at`,
`required_lesson`, `is_published`.

Lesson types: `text`, `video`, `material`, `mixed`, `external_link`.
Release types: `always`, `after_previous`, `after_lesson`, `date`.

### Reorder

```http
POST /api/v1/courses/{id}/structure/reorder/
```

```json
{
  "type": "lesson",
  "items": [
    {"id": 12, "order": 1},
    {"id": 15, "order": 2},
    {"id": 14, "order": 3}
  ]
}
```

`type` is `module`, `topic` or `lesson`. IDs must belong to one parent and
orders must form a unique continuous sequence starting at 1. The operation is
atomic and failures use `invalid_structure_order`.

### Materials

For file materials, send `multipart/form-data` with `title`, optional
`description`, `type`, `file` and optional `download_allowed`. For
`external_link` or `library_link`, send JSON with `external_url` and no file.

Supported material types are `pdf`, `doc`, `docx`, `ppt`, `pptx`, `image`,
`audio`, `video`, `external_link`, `library_link`, `other`. Responses never
expose the internal file path. They return controlled `download_url` and, for
a ready video, `playback_url`.

`GET /api/v1/courses/{id}/materials/` supports `search`, `type`, `lesson` and
`module`.

## 6. Enrollment and Student contract

### Manual enrollment

```json
{
  "student": 20,
  "source": "manual",
  "external_sis_id": ""
}
```

Only active users with the Student role are accepted. Repeating an existing
active enrollment returns `already_enrolled`; a previously inactive enrollment
may be reactivated.

### Student Course and lesson availability

The Student Course response contains metadata, `overall_progress`, and nested
modules/topics/lessons. Each lesson includes:

```json
{
  "id": 20,
  "title": "Lesson 1",
  "status": "not_started",
  "is_available": false,
  "lock_reason": "Complete the previous lesson.",
  "content": null,
  "materials": []
}
```

The backend is authoritative for `is_available` and `lock_reason`. The frontend
must not reconstruct release rules. Locked content and materials are omitted.

Starting and completing a lesson return:

```json
{
  "id": 7,
  "course_id": 1,
  "lesson_id": 20,
  "status": "completed",
  "started_at": "2026-08-14T10:00:00+06:00",
  "completed_at": "2026-08-14T10:30:00+06:00",
  "updated_at": "2026-08-14T10:30:00+06:00"
}
```

Both transitions are idempotent. A completed lesson is never regressed by
calling start again.

### Student progress and dashboard

Course progress:

```json
{
  "course_id": 1,
  "total_lessons": 10,
  "completed_lessons": 4,
  "progress_percent": 40
}
```

Dashboard fields are `active_courses`, `completed_lessons`,
`overall_progress`, `continue_learning`, `courses`, and `upcoming_events`.
`continue_learning` is `{}` when no eligible lesson exists.

## 7. Calendar contract

Staff create/PATCH payload:

```json
{
  "course": 1,
  "title": "Module released",
  "description": "Module 2 is available",
  "event_type": "module_release",
  "start_at": "2026-09-10T09:00:00+06:00",
  "end_at": null,
  "is_public": true
}
```

Event types are `course_start`, `course_end`, `module_release`,
`lesson_release`, `custom`. `end_at` cannot precede `start_at`. Staff and
Student lists accept `date_from`, `date_to`, `course`, `event_type`, `page`,
`page_size`. Students receive only public events for their active Published
courses.

## 8. Supporting admin endpoints

The LMS Admin user-management screen may use:

- `GET/POST /api/v1/users/` with `search`, role/status filters and pagination;
- `GET /api/v1/users/{id}/`;
- `GET /api/v1/roles/`.

These endpoints require `lms_admin` or `super_admin`. Organization CRUD is not
implemented in Release 1; `/api/v1/organization/` is currently a reserved
namespace, so organization selectors must use seeded IDs or another agreed
source until that API is added.

## 9. Known Release 1 limitations

- Teacher Dashboard and Admin Dashboard are composed from existing resources;
  dedicated aggregate endpoints are not implemented.
- Course Preview is composed from Course detail, structure and materials.
- Organization has models and Admin support but no REST CRUD API.
- OIDC is provider-ready architecture only; JWT login remains the active flow.
- SIS integration provides the backend sync boundary, not a frontend screen.
- Assignment, Quiz, Gradebook, Attendance and analytics are outside this
  Release 1 contract.
