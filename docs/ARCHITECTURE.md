# SU LMS Backend Architecture

## 1. Scope

This document describes the backend architecture prepared for Release 1. The
project is a Django monolith with domain-oriented Django apps and a versioned
REST API under `/api/v1/`.

Release 1 introduces new LMS domain boundaries alongside the existing legacy
apps. Legacy models and endpoints remain available until their consumers are
migrated and compatibility is confirmed. New code must not add dependencies
from Release 1 domains back to legacy business models unless an explicit
integration task requires it.

## 2. Application map

### Release 1 foundation

| App | Responsibility | Current state |
|---|---|---|
| `api` | API v1 root, health check, OpenAPI integration and common error handling | Active |
| `accounts` | Custom user, JWT authentication, current-user endpoint, roles and base User API | Active |
| `audit` | Shared abstract audit model and Django Admin audit mixin | Active |
| `organization` | Faculties, departments, academic programs, student groups and semesters | Active models and Admin; API deferred |
| `courses` | Release 1 course metadata and Course list/create/detail API | Active |
| `enrollments` | Future enrollment ownership and lifecycle | Reserved; no models yet |
| `learning` | Ordered course modules, topics, lessons and release conditions | Active models, Admin and structure management API |
| `progress` | Future student progress and completion state | Reserved; no models yet |

The project follows its existing top-level Django app layout. The new apps are
therefore located beside `accounts`, `core`, `attendance`, `finance` and
`result`, rather than under an additional `apps/` Python package.

### Infrastructure and framework apps

| Component | Responsibility |
|---|---|
| `config` | Django settings, URLs, database configuration and configuration tests |
| Django REST Framework | REST request/response lifecycle, authentication and permissions |
| Simple JWT | Access and refresh JWT handling, rotation and blacklist |
| django-filter | Course and User API filtering |
| drf-spectacular | OpenAPI schema and Swagger/ReDoc pages |
| django-cors-headers | Explicit frontend origin and credential handling |
| WhiteNoise | Static-file serving support |
| Django Admin / JET | Administrative interface |

## 3. Main Release 1 models

### Accounts

- `accounts.User` is the project authentication model;
- `accounts.Role` contains stable role codes;
- `accounts.UserRole` assigns roles to users;
- legacy boolean role flags remain temporarily supported for compatibility;
- `accounts.Student`, `accounts.Lecturer` and the legacy `accounts.Group`
  remain available to existing modules.

### Audit

`audit.AuditModel` is abstract and supplies:

- `created_at`;
- `updated_at`;
- `created_by`;
- `updated_by`.

User references are nullable and use `SET_NULL`, so deleting a user does not
delete domain data. `audit.admin.AuditAdminMixin` fills the user fields for
changes made through Django Admin. API serializers and services must assign
the acting user explicitly. Detailed usage is documented in
[`AUDIT_MODEL.md`](AUDIT_MODEL.md).

### Organization

The `organization` app owns the new academic structure:

```text
Faculty
  └── Department
       └── Program
            └── Group

Semester
```

- `Faculty` has a globally unique `code`;
- `Department.code` is unique within a Faculty;
- `Program.code` is unique within a Department;
- `Group` is unique by Program, name and admission year;
- `Semester` stores a named date range and validates that the end date is not
  before the start date;
- important parent relationships use `PROTECT` to prevent accidental deletion
  of referenced academic structures.

Organization models are available in Django Admin. A public Organization API
is not part of the current foundation scope.

### Courses

`courses.Course` is the Release 1 course model. It contains:

- identity: `title`, globally unique `code`, `description`;
- academic metadata: `language`, `credits`, `semester`;
- organization scope: `faculty`, `department`, `program`;
- lifecycle: `draft`, `under_review`, `needs_revision`, `published`, `archived`;
- schedule: `start_date`, `end_date`;
- files: `cover`, `syllabus`;
- common audit fields.

The selected Department must belong to the selected Faculty, and the selected
Program must belong to that Department. Archived courses reject ordinary
model saves and Django Admin changes. An intentional maintenance correction
must use the explicit archived-update path.

Teacher and Course Assistant assignments use `CourseTeachingAssignment`.
Lifecycle transitions are atomic, permission-controlled operations and create
immutable `CourseStatusHistory` records. Publication stores `published_at` and
`published_by`; a return for revision preserves the reviewer comment.

Quiz, Gradebook and Assignment are outside Release 1. Course structure is
owned separately by the `learning` app rather than being embedded in Course.

### Learning structure

`learning` owns the ordered hierarchy `Course -> CourseModule -> CourseTopic
-> Lesson`. The database enforces unique positive order values within each
parent. Modules support `always`, `after_previous` and `date` release modes.
Lessons add `after_lesson`, with validation that prevents self-references,
cross-course prerequisites and dependency cycles. Prerequisite lessons use
`PROTECT`; the normal Course-to-Lesson hierarchy uses cascade deletion. All
three models inherit the shared audit fields and are registered in Django
Admin.

`LearningMaterial` belongs to both a Lesson and its Course. Model validation
prevents those two ownership paths from referring to different courses. It
stores a local file or external URL together with original filename, MIME
type, size, extension and download policy metadata. Release 1 supports PDF,
DOC, DOCX, PPT, PPTX, image, audio, video, external link, library link and
other material types. Materials inherit the shared audit fields and are
registered in Django Admin; upload and download validation is handled by the
materials API layer.

## 4. Organization and Course relationships

```text
organization.Faculty      ─┐
                           ├── courses.Course
organization.Department  ─┤
organization.Program     ─┤
organization.Semester    ─┘

accounts.User ── created_by / updated_by ── courses.Course
accounts.User ── created_by / updated_by ── Organization models
```

All Course-to-Organization foreign keys use `PROTECT`. Removing an academic
entity that is referenced by a course must be an explicit migration or
archival operation, not a cascading delete.

## 5. API v1

The versioned API is mounted in `api.v1.urls`:

| Endpoint | Purpose | Access |
|---|---|---|
| `GET /api/v1/` | API metadata and resource namespaces | Public |
| `GET /api/v1/health/` | Application and database readiness | Public |
| `/api/v1/auth/` | Login, refresh, logout and current user | Endpoint-specific |
| `/api/v1/users/` | Base user list/create/detail operations | Role-based |
| `GET /api/v1/roles/` | Stable role catalogue | Authenticated/role-based |
| `GET /api/v1/courses/` | Paginated searchable and filterable course list | Authenticated |
| `POST /api/v1/courses/` | Create a course | Staff/admin |
| `GET /api/v1/courses/{id}/` | Retrieve course metadata | Authenticated |
| `GET /api/v1/courses/{id}/readiness/` | Course readiness score and checks | Course view permission |
| `GET /api/v1/courses/{id}/structure/` | Nested Module, Topic and Lesson structure | Course view permission |
| `POST /api/v1/courses/{id}/structure/reorder/` | Atomically reorder sibling modules, topics or lessons | Structure-manage permission |
| `POST /api/v1/courses/{id}/modules/` | Append or explicitly order a module | Structure-manage permission |
| `PATCH /api/v1/modules/{id}/` | Update module metadata and release settings | Structure-manage permission |
| `DELETE /api/v1/modules/{id}/` | Safely delete a module | Structure-manage permission |
| `POST /api/v1/modules/{id}/topics/` | Append or explicitly order a topic | Structure-manage permission |
| `PATCH /api/v1/topics/{id}/` | Update topic metadata and order | Structure-manage permission |
| `DELETE /api/v1/topics/{id}/` | Safely delete a topic | Structure-manage permission |
| `POST /api/v1/topics/{id}/lessons/` | Append or explicitly order a lesson | Structure-manage permission |
| `GET /api/v1/lessons/{id}/` | Retrieve lesson metadata and content | Structure-view permission |
| `PATCH /api/v1/lessons/{id}/` | Update lesson and release conditions | Structure-manage permission |
| `DELETE /api/v1/lessons/{id}/` | Delete an unreferenced lesson | Structure-manage permission |
| `POST /api/v1/courses/{id}/submit-review/` | Submit Draft/Needs Revision course | Submit-review permission |
| `POST /api/v1/courses/{id}/return-for-revision/` | Return Under Review course with a comment | Review permission |
| `POST /api/v1/courses/{id}/publish/` | Publish an Under Review course | Publish permission |
| `POST /api/v1/courses/{id}/archive/` | Archive a Published course | Archive permission |
| `POST /api/v1/courses/{id}/restore/` | Restore an Archived course | Archive permission |
| `/api/v1/organization/` | Reserved Organization namespace | API deferred |

Course list filtering supports `status`, `semester`, `faculty`, `department`,
`program`, `teacher`, `language` and `created_by`. Search covers `title`,
`code`, `description` and assigned teacher names. Ordering is limited to
`title`, `code`, `created_at`, `updated_at`, `start_date`, `end_date` and
`status`; `page` and `page_size` control pagination.

Course readiness evaluates required metadata, active Organization relations,
an active primary teacher, the optional syllabus and a minimum structure of
Module, Topic and Lesson. Metadata, teacher and structure failures block
review submission; a missing syllabus is reported as a warning and lowers the
score without blocking submission. Lesson-material checks are added to the
same service when learning materials become available.

Deleting an empty module needs no confirmation. Deleting a module containing
topics requires a JSON body of `{"confirm": true}`; otherwise the API returns
`409 structure_not_empty`. Even a confirmed deletion is rejected when one of
the module's lessons is a prerequisite for a lesson outside that module.
Topic deletion follows the same confirmation contract and rejects a cascade
when one of its lessons is required by a lesson outside the topic.
Lesson writes validate type, order, date releases and prerequisite ownership.
Self-references, cross-course prerequisites and dependency cycles return a
validation error. Deleting a prerequisite used by another lesson returns
`409 lesson_is_required`.

Structure reordering accepts a `type` of `module`, `topic` or `lesson` and a
complete sibling list in `items`. IDs and order values must be unique, all
items must have the same parent, and order values must be the continuous
sequence `1..N`. The operation locks the course and affected rows and commits
as one transaction. Invalid or incomplete input returns the stable error code
`invalid_structure_order` without a partial reorder.

## 6. Database and runtime

PostgreSQL is the primary development and staging database. `DATABASE_URL`
takes precedence over individual `DB_*` variables. SQLite remains available
only when explicitly selected for isolated tests.

The optional Docker Compose environment contains:

- `backend` on port `8000`;
- PostgreSQL 16 on container port `5432` and default host port `5433`;
- health checks for both services;
- persistent PostgreSQL and media volumes.

Local environment setup is documented in [`LOCAL_SETUP.md`](LOCAL_SETUP.md).

## 7. Legacy apps outside the new LMS domain foundation

The following existing apps are not being redesigned as part of this Release
1 foundation:

| Legacy app | Existing responsibility | Release 1 treatment |
|---|---|---|
| `core` | Legacy Course, Program, AcademicYear, Semester, CourseAllocation and Notification | Preserved for compatibility; new code uses `courses` and `organization` |
| `attendance` | Lesson times, schedules and attendance records tied to legacy Course/Group | Preserved; migration to new domains is deferred |
| `result` | Module and semester grade records tied to legacy Course | Preserved; Gradebook redesign is out of scope |
| `finance` | Contracts, payments and accounting workflows | Preserved; outside LMS domain foundation |

Some legacy models also remain in `accounts`, including the old Group and
profile structures. They must not be silently replaced with
`organization.Group`; a later data migration and API compatibility plan is
required.

Legacy endpoints such as `/api/courses/` remain registered. The new Course API
is `/api/v1/courses/` and uses `courses.Course`.

## 8. Explicitly deferred work

The following functionality is outside the current foundation:

- Organization CRUD API;
- Enrollment API;
- learning objects and SCORM;
- assignments, quizzes and Gradebook;
- student progress and calendar;
- course publication workflow beyond the base status field;
- course copying and templates;
- Teacher Portal and Student Progress APIs;
- S3 or another remote file-storage integration;
- complete field-level Audit Log.

These features should be implemented in their corresponding domain apps
instead of expanding the legacy `core` app.
