# SU-LMS Release 1 backend status

Актуально на: **2026-08-15**  
Ветка разработки: `feature/SULMS-release1-core-backend`

Документ фиксирует фактическую готовность backend Release 1. Статус `DONE`
означает, что требуемая функциональность реализована и имеет профильные тесты.
Он не заменяет финальный regression, security и fresh-database прогон перед PR.

## Статусы

| Status | Значение |
|---|---|
| `DONE` | Требование реализовано и покрыто профильными тестами |
| `PARTIAL` | Рабочая основа есть, но остаётся обязательная проверка или ограничение |
| `READY_FOR_PROVIDER` | Интеграционная граница готова, нужны внешние credentials/contract |
| `PENDING` | Работа входит в текущий план, но финальная проверка ещё не выполнена |
| `OUT_OF_SCOPE` | Явно исключено из Release 1 текущим ТЗ |

## Матрица готовности

| Requirement | Status | Endpoint / Model | Tests | Known limitations |
|---|---|---|---|---|
| API v1 и health check | `DONE` | `GET /api/v1/`, `GET /api/v1/health/` | `api/tests/test_health.py`, API routing tests | Health сообщает только состояние приложения и основной БД |
| JWT authentication | `DONE` | `/api/v1/auth/login/`, `refresh/`, `logout/`, `me/` | `accounts/tests/test_auth_v1.py`, cookie/security tests | Университетский SSO пока не активен |
| Users, roles и permissions | `DONE` | `/api/v1/users/`, `/api/v1/roles/`; `User`, `Role`, `LMSPermission` | accounts API, role и permission tests | User API предназначен для LMS Admin/Super Admin |
| Organization foundation | `DONE` | `Faculty`, `Department`, `Program`, `Group`, `Semester` | `organization/tests/test_models.py`, seed tests | REST CRUD Organization не входит в текущий Release 1 |
| Course CRUD | `DONE` | `GET/POST /api/v1/courses/`, `GET/PATCH/DELETE /api/v1/courses/{id}/`; `Course` | `courses/tests/test_api_v1.py` | Удаление разрешено только для Draft; Archived изменяется только отдельной логикой |
| Course filters и object access | `DONE` | Course list filters/search/order; `courses_accessible_to()` | Course filter, search, permission и foreign-object tests | Teacher видит только назначенные курсы без глобальной роли |
| Course lifecycle | `DONE` | `submit-review`, `return-for-revision`, `publish`, `archive`, `restore` | `courses/tests/test_lifecycle.py`, API lifecycle tests | Workflow намеренно ограничен статусами Release 1 |
| Course readiness | `DONE` | `GET /api/v1/courses/{id}/readiness/` | `courses/tests/test_readiness.py` | Проверяет Release 1 metadata/structure/material rules, не Gradebook |
| Course History | `DONE` | `GET /api/v1/courses/{id}/history/`; `CourseHistoryEvent` | `courses/tests/test_history_api.py`, audit tests | Это domain history курса, не универсальный field-level audit log |
| Course Structure | `DONE` | Course structure, Module/Topic/Lesson CRUD и reorder endpoints | `learning/tests/test_api_v1.py` | Массовый редактор структуры использует один атомарный reorder endpoint |
| Release conditions | `DONE` | `ReleaseType`, `required_lesson`, lesson availability | Learning model/API/availability tests | Нет сложных cohort- или grade-based условий |
| Learning Materials | `DONE` | Lesson material CRUD, course material list, controlled download | `learning/tests/test_material_api.py`, file validation tests | Файлы выдаются только через permission-aware endpoints |
| Video foundation | `PARTIAL` | `VideoProcessingService`, `/materials/{id}/playback/` | `learning/tests/test_video_processing.py`, material API tests | Есть синхронный metadata/duration probe и статусы; async transcoding worker отсутствует |
| SCORM Basic | `DONE` | `ScormPackage`, upload/detail/content endpoints | `learning/tests/test_scorm_api.py`, `learning/tests/test_scorm_validation.py` | Нет SCORM runtime tracking, Gradebook и расширенной аналитики — это не требуется Release 1 |
| Course Copy | `DONE` | `POST /api/v1/courses/{id}/copy/` | Course copy tests | Файлы ссылаются на существующие storage objects; enrollment/progress/history не копируются |
| Course Templates | `DONE` | `/api/v1/course-templates/`, `create-course/`; `CourseTemplate` | Course template tests | Update/delete template endpoints отложены |
| Enrollment | `DONE` | `/api/v1/courses/{id}/enrollments/`; `Enrollment` | enrollment model/API tests | Bulk UI import не входит в ручной endpoint |
| Student Courses | `DONE` | `/api/v1/student/courses/`, `/courses/{id}/` | `enrollments/tests/test_api_v1.py` | Возвращаются только активные enrollment на Published-курсы |
| Basic Progress | `DONE` | Student dashboard/progress/start/complete endpoints; `LessonProgress` | `progress/tests/test_api_v1.py` | Нет Gradebook, оценок и learning analytics |
| Calendar | `DONE` | `/api/v1/calendar/events/`, `/api/v1/student/calendar/`; `CalendarEvent` | `calendar_events/tests/test_calendar_api.py` | Нет внешней календарной синхронизации |
| Audit fields | `DONE` | `AuditModel`, `AuditAdminMixin` | audit и model/admin tests | Полный field-level Audit Log отложен |
| SIS Integration | `READY_FOR_PROVIDER` | `POST /api/v1/integrations/sis/enrollments/sync/`; `SISSyncEvent` | `enrollments/tests/test_sis_api.py` | Idempotent sync contract готов; реальный SIS transport и provider mapping ещё не предоставлены |
| OIDC / university SSO | `READY_FOR_PROVIDER` | `OIDCConfiguration`, `OIDCService` | `accounts/tests/test_oidc.py` | Нужны issuer metadata, client credentials, callback и claims contract университета |
| Seed Release 1 | `DONE` | `python manage.py seed_release1` | `accounts/tests/test_seed_release1.py` | Только development/demo; создаётся 9 курсов, чтобы студент мог иметь 4 Published enrollment |
| Django Admin | `DONE` | Все обязательные Release 1 models зарегистрированы | model/admin registration tests | Admin используется для development/debug и не заменяет REST API |
| Docker/PostgreSQL | `DONE` | `Dockerfile`, `docker-compose.yml`, PostgreSQL 16 | `config/tests/test_database.py`; Compose healthchecks | Автоматизированный production-container smoke test не входит в текущий CI |
| Frontend API contract | `DONE` | `docs/FRONTEND_API_CONTRACT.md` | Проверена карта всех обязательных экранов | Teacher/Admin dashboards и Course Preview собираются из существующих ресурсов |
| OpenAPI / Swagger | `PARTIAL` | `/api/schema/`, `/api/docs/`, `/api/schema/redoc/` | Schema generation/validation tests | Нужен финальный аудит examples, multipart, filters, permissions и possible errors |
| Unified API errors | `PARTIAL` | `api.v1.exceptions.custom_exception_handler` | `api/tests/test_errors.py` и domain error tests | Нужна финальная сверка всех минимальных кодов ТЗ и aliases authentication errors |
| CI и coverage | `PARTIAL` | `.github/workflows/django.yml`, `pylint.yml`, `.coveragerc` | CI выполняет check, migrations, schema, full tests и coverage | `calendar_events` ещё нужно включить в Release 1 coverage source |
| Fresh database flow | `PENDING` | `migrate -> seed_release1 -> check/runserver` | Будет проверено на чистой PostgreSQL database | Нужен отдельный финальный прогон без ручных изменений |
| Security/secrets audit | `PENDING` | settings, environment, repository history/worktree | Запланирован отдельный scan | Финальный аудит перед PR ещё не выполнен |
| Full regression and Definition of Done | `PENDING` | Полный Release 1 backend | `python manage.py test`, coverage, OpenAPI, lint | Выполняется после оставшихся Swagger/error/CI задач |

## Известные ограничения Release 1

- Organization представлен моделями и Django Admin, но не REST CRUD API.
- Teacher Dashboard, Admin Dashboard и Course Preview собираются frontend из
  существующих API; отдельных aggregate endpoints нет.
- Video processing использует заменяемый синхронный service interface без
  очереди и полноценного transcoding pipeline.
- OIDC нельзя завершить без параметров университетского Identity Provider.
- SIS endpoint и идемпотентная обработка готовы, но подключение к реальному SIS
  требует его transport, credentials и mapping.
- Course History не является универсальным field-level журналом всех моделей.
- Production deployment, monitoring и external calendar sync не входят в
  текущую задачу.

## Явно вне текущего scope

В соответствии с ТЗ в Release 1 не реализуются:

- Assignments, Submissions, Rubrics, Gradebook и Appeals;
- Quiz Engine, Question Bank, Attempts и Auto Grading;
- Attendance и QR Attendance;
- Forum, Chat и Internal Messaging;
- Learning Analytics, Risk Prediction и Heatmap;
- AI Tutor и AI Generator;
- Certificates;
- отдельные mobile-specific API.

Legacy apps `finance`, `attendance`, `result`, parent flows и их данные
сохраняются для совместимости и не переписываются в рамках Release 1.

## Что осталось перед Pull Request

1. Завершить OpenAPI/Swagger contract audit.
2. Сверить и дополнить минимальные error codes.
3. Включить `calendar_events` в coverage и CI-проверку Release 1.
4. Проверить fresh PostgreSQL database flow.
5. Выполнить secrets/security audit.
6. Запустить полный набор tests, coverage, migrations, OpenAPI и lint.
7. Создать Pull Request в `develop`.
