# SU LMS Backend Architecture

## 1. Scope

This document describes the backend architecture prepared for Release 1. The
project is a Django monolith with domain-oriented Django apps and a versioned
REST API under `/api/v1/`.

The screen-to-endpoint mapping, payload examples, permissions and stable error
codes used by the web client are documented in
[`FRONTEND_API_CONTRACT.md`](FRONTEND_API_CONTRACT.md).

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
| `audit` | Shared audit fields, Admin mixin and common Course History events | Active |
| `organization` | Faculties, departments, academic programs, student groups and semesters | Active models and Admin; API deferred |
| `courses` | Course metadata, lifecycle, copying, templates and management API | Active |
| `enrollments` | Student-to-course membership, management API, student course access and SIS sync boundary | Active |
| `learning` | Ordered course modules, topics, lessons and release conditions | Active models, Admin and structure management API |
| `progress` | Lesson progress, completion, student progress and dashboard APIs | Active |
| `calendar_events` | Course events and staff/student Calendar APIs | Active model, Admin and API |

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

#### OIDC/SSO integration boundary

The existing JWT login, refresh, logout and current-user endpoints remain the
active Release 1 authentication flow. `accounts.oidc.OIDCService` provides a
provider-neutral boundary for a future university Identity Provider: it
validates configuration, derives the standard discovery URL and prepares
Authorization Code Flow parameters with optional PKCE. It does not perform
network calls or expose `OIDC_CLIENT_SECRET`.

OIDC is disabled by default. When `OIDC_ENABLED=True`, Django's security checks
require `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` and
`OIDC_REDIRECT_URI` to be configured with valid absolute URLs where applicable.
Provider discovery, callback endpoints, claim mapping and token exchange must
be added once the university supplies its issuer metadata, credentials and
claim contract. No provider-specific value is hardcoded in the application.

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

### Enrollments

`enrollments.Enrollment` connects an `accounts.User` student to a Release 1
Course. It records the `active`, `completed`, `withdrawn` or `suspended`
lifecycle state, distinguishes manual enrollment from SIS synchronization and
can retain an external SIS identifier. The model uses the shared audit fields
and is available in Django Admin. A database constraint permits only one
lifecycle record for each Student and Course pair; reenrollment reactivates
that record instead of creating a duplicate. The course Enrollment API uses
method-specific `enrollments.view` and `enrollments.manage` permissions plus
object-level Course access. A duplicate active enrollment returns the stable
`already_enrolled` error; posting a withdrawn, suspended or completed pair
reactivates the existing record atomically.

The Student Course query is centralized in
`enrollments.querysets.student_courses_queryset`. It returns only Published
courses for which the current user has an Active enrollment. Draft, Under
Review, Archived, withdrawn and other students' courses therefore resolve to
404 at the detail endpoint and never appear in the list. Student serializers
exclude review, publication-owner and audit fields. Nested structure, lesson
availability and safe material metadata are included in Student Course Detail.
Only published lessons are exposed. Each lesson contains `status`,
`is_available` and `lock_reason`; release checks use the prefetched hierarchy
without per-lesson queries. `LessonProgress` stores operational lesson state
and drives these response fields directly.
Protected material download and video playback accept an enrolled Student but
continue to reject users without an Active enrollment in the Published course.

The Student Progress API exposes idempotent lesson start/completion actions,
per-course progress and an aggregate student summary. It only reads Published
courses with an Active enrollment. Lesson actions enforce server-side release
conditions; locked lessons return a stable `lesson_locked` conflict response.
The summaries are operational UI state, not learning analytics.
Course progress is the number of completed lessons divided by the currently
available Published lessons, rounded to the nearest whole percent. Locked and
unpublished lessons are excluded. The same calculation and progress records
drive `overall_progress`, lesson `status` and availability in Student Course
Detail, so the frontend does not need to reconcile competing data sources.

`GET /api/v1/student/dashboard/` combines those summaries into the Release 1
dashboard contract. `continue_learning` prefers the most recently updated
available In Progress lesson and otherwise selects the first available
unfinished lesson. It is an empty object when there is nothing to continue.
`upcoming_events` contains the next five public future events visible through
the Student Calendar access policy.

### Calendar

`calendar_events.CalendarEvent` attaches a scheduled item to a Course and
supports `course_start`, `course_end`, `module_release`, `lesson_release` and
`custom` types. An optional end cannot precede the start. The `(course,
start_at)` index supports course timeline reads, and shared audit fields record
the staff actor.

Staff Calendar CRUD uses `calendar.view`/`calendar.manage` together with
object-level Course scope. The Student Calendar is read-only and exposes only
public events belonging to the student's Active Published courses. Both lists
support `date_from`, `date_to`, `course` and `event_type` filters and standard
pagination.

### SIS enrollment integration

`SISIntegrationService` is the transport-independent integration boundary for
SIS enrollment events. It resolves a student by `accounts.Student.id_number`
and a course by its case-insensitive `Course.code`, then enrolls, reactivates or
withdraws the existing enrollment lifecycle record. `SISSyncEvent` stores each
processed event under a unique `external_event_id`, making retries idempotent.
Repeating the same payload returns the stored result; reusing an event ID with
a different payload returns a conflict. Failed events are rolled back together
with their journal entry, so they can be retried after the source data is fixed.

The development/admin endpoint is intentionally protected by the existing
`enrollments.manage` permission. A production SIS transport can call the same
service later without coupling credentials or vendor-specific code to the LMS
domain layer.

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
| `GET /api/v1/courses/{id}/history/` | Paginated course and content history | Course view permission and object scope |
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
| `GET /api/v1/lessons/{id}/materials/` | List lesson materials | Materials-view permission |
| `POST /api/v1/lessons/{id}/materials/` | Upload a file or add a link | Materials-upload permission |
| `GET /api/v1/materials/{id}/` | Retrieve material metadata | Materials-view permission |
| `PATCH /api/v1/materials/{id}/` | Update material metadata or source | Materials-edit permission |
| `DELETE /api/v1/materials/{id}/` | Delete a material record | Materials-delete permission |
| `GET /api/v1/materials/{id}/download/` | Permission-checked file download | Materials-view permission and download policy |
| `GET /api/v1/materials/{id}/playback/` | Stream a ready video from private storage | Materials-view permission and course access |
| `GET, POST /api/v1/lessons/{id}/scorm-packages/` | List or upload SCORM packages | Materials-view/upload permission |
| `GET /api/v1/scorm-packages/{id}/` | Retrieve SCORM metadata and launch URL | Materials-view permission and course access |
| `GET /api/v1/scorm-packages/{id}/content/{path}` | Stream a launch file or package asset | Materials-view permission and course access |
| `GET /api/v1/courses/{id}/materials/` | Search and filter all course materials | Materials-view permission |
| `POST /api/v1/courses/{id}/submit-review/` | Submit Draft/Needs Revision course | Submit-review permission |
| `POST /api/v1/courses/{id}/return-for-revision/` | Return Under Review course with a comment | Review permission |
| `POST /api/v1/courses/{id}/publish/` | Publish an Under Review course | Publish permission |
| `POST /api/v1/courses/{id}/archive/` | Archive a Published course | Archive permission |
| `POST /api/v1/courses/{id}/restore/` | Restore an Archived course | Archive permission |
| `POST /api/v1/courses/{id}/copy/` | Copy course metadata and content into a new Draft | Copy permission and course access |
| `GET /api/v1/courses/{id}/enrollments/` | Paginated course enrollment list | Enrollment-view permission and course access |
| `POST /api/v1/courses/{id}/enrollments/` | Manually enroll or reactivate a Student | Enrollment-manage permission and course access |
| `GET /api/v1/student/courses/` | Paginated courses available to the current Student | Student role and course-view permission |
| `GET /api/v1/student/courses/{id}/` | Safe enrolled Course metadata | Student role and active enrollment |
| `GET /api/v1/student/lessons/{id}/` | Safe lesson detail with availability, progress and materials | Student role, active enrollment and Published course |
| `POST /api/v1/student/lessons/{id}/start/` | Idempotently mark an available lesson in progress | Student role and active enrollment |
| `POST /api/v1/student/lessons/{id}/complete/` | Idempotently complete an available lesson | Student role and active enrollment |
| `GET /api/v1/student/progress/` | Aggregate operational progress for the Student | Student role and active enrollments |
| `GET /api/v1/student/courses/{id}/progress/` | Operational progress for one enrolled course | Student role and active enrollment |
| `GET /api/v1/student/dashboard/` | Release 1 course, progress and continue-learning summary | Student role |
| `GET, POST /api/v1/calendar/events/` | Scoped staff Calendar list/create | Calendar view/manage permission and Course access |
| `GET, PATCH, DELETE /api/v1/calendar/events/{id}/` | Scoped staff Calendar detail/update/delete | Calendar view/manage permission and Course access |
| `GET /api/v1/student/calendar/` | Public events for Active Published enrolled courses | Student role and calendar-view permission |
| `POST /api/v1/integrations/sis/enrollments/sync/` | Idempotently apply an SIS enroll/withdraw event | Enrollment-manage permission |
| `GET, POST /api/v1/course-templates/` | List active templates or snapshot an accessible course | Copy permission |
| `GET /api/v1/course-templates/{id}/` | Retrieve active template metadata | Copy permission |
| `POST /api/v1/course-templates/{id}/create-course/` | Create a new Draft from an active template | Copy and create permissions |
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

Student lesson availability is calculated centrally by
`learning.availability.evaluate_lesson_availability`. It evaluates publication,
module and lesson dates, previous-module completion, previous-lesson completion
and explicit lesson prerequisites, and returns `is_available` plus a stable
`lock_reason`. The caller supplies completed lesson IDs; the Student Course API
will source them from `LessonProgress` when the progress API is introduced.

Material responses expose metadata, an external URL where applicable and a
protected `download_url`; the underlying storage path is write-only. Course
material filtering supports `search`, `type`, `lesson` and `module`. All
operations require both the corresponding `materials.*` permission and object
access to the owning course. Writes also follow the course editability rules,
and downloads enforce `download_allowed` before opening the storage object.
Uploads are limited by `MATERIAL_MAX_UPLOAD_SIZE_MB` (100 MB by default). The
validation service rejects empty files, executable and deceptive double
extensions, mismatched material types, invalid file signatures and conflicting
declared MIME types. Trusted metadata is derived from validated bytes rather
than accepted from the request.

Video materials use the `VideoProcessingService` boundary so processing is not
coupled to models or API views. The Release 1 implementation validates the
upload, records `uploaded`, `processing`, `ready` or `failed`, and extracts an
integer `duration_seconds` from MP4/MOV containers when their metadata is
available. It currently serves the validated original file and does not
transcode. A `playback_url` is returned only for a ready video and points to the
permission-checked `GET /api/v1/materials/{id}/playback/` endpoint; raw storage
URLs remain unavailable. The service interface can later be backed by an
asynchronous transcoding worker without moving processing into model or view
logic.

`ScormPackage` provides the Release 1 SCORM foundation. Upload validation
requires a real ZIP with a root `imsmanifest.xml`, parses its schema version and
selects an existing SCO launch resource. Unsafe paths, duplicate names,
encrypted entries, XML declarations capable of entity expansion, excessive
file counts, decompressed size and compression ratio are rejected. Packages
remain in private storage; launch HTML and relative assets are streamed from
the archive through authenticated endpoints without extraction to disk. Launch
responses use a sandboxed Content Security Policy and configurable
`SCORM_FRAME_ANCESTORS`. Gradebook integration, runtime tracking and advanced
SCORM analytics are intentionally deferred.

Course copies are created by the atomic `courses.copying.copy_course` service.
It produces a new Draft with copied metadata, modules, topics, lessons, release
rules and learning-material metadata. Lesson dependencies are remapped to the
new lesson IDs, and lesson publication flags are reset. Stored course and
material file objects are referenced rather than physically duplicated. Review
state, publication metadata, teaching assignments, SCORM packages, enrollments,
progress and audit history are not copied. The operation requires
`courses.copy` plus object access to the source course and rolls back completely
if any nested object cannot be created.

`CourseTemplate` stores a versioned JSON snapshot of the same course metadata
and learning structure used by course copying. The snapshot contains portable
lesson references, so prerequisite links are remapped when a course is
created. A template has no foreign key to its source Course and remains usable
after that source is deleted. Only active templates are exposed by the API.
Creating a template requires `courses.copy` and access to the source; creating
a new Draft from it additionally requires `courses.create`. Snapshot creation
and restoration are atomic. Review/publication state, teaching assignments,
SCORM packages, enrollments, progress and audit history are excluded. Stored
file names are referenced and file bytes are not physically duplicated.

## 6. Database and runtime

PostgreSQL is the primary development and staging database. `DATABASE_URL`
takes precedence over individual `DB_*` variables. SQLite remains available
only when explicitly selected for isolated tests.

Media files use Django's storage interface. `USE_S3=False` selects local file
storage; `USE_S3=True` selects the `django-storages` S3 backend, supporting AWS
S3, MinIO and compatible services through `S3_ENDPOINT_URL`, bucket, region and
addressing-style settings. Credentials are read only from environment variables
or boto3's runtime IAM credential chain.

Learning material uploads use the dedicated `private` storage alias. Locally it
stores files under `PRIVATE_MEDIA_ROOT`, outside the publicly served
`MEDIA_ROOT`; in S3 it uses the `private` key prefix. Both private backends
deliberately reject direct URL generation. A client can obtain file bytes only
from `GET /api/v1/materials/{id}/download/`, which checks authentication, the
`materials.view` permission, access to the owning course and
`download_allowed` before opening the storage object. The default public
storage remains available for non-sensitive media.

The optional Docker Compose environment contains:

- `backend` on port `8000`;
- PostgreSQL 16 on container port `5432` and default host port `5433`;
- health checks for both services;
- persistent PostgreSQL, public media and private material volumes.

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

- assignments, quizzes and Gradebook;
- course-template update and delete endpoints;
- dedicated Teacher/Admin dashboard aggregate endpoints;
- Organization REST CRUD;
- complete field-level Audit Log beyond the common Course History feed.

These features should be implemented in their corresponding domain apps
instead of expanding the legacy `core` app.
