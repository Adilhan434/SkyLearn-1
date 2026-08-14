# SU-LMS Backend

Backend системы управления обучением SU-LMS. Проект построен как Django-монолит
с разделением Release 1 по доменам и версионированным REST API под
`/api/v1/`.

Основные возможности Release 1:

- JWT-аутентификация и роли;
- управление курсами и их жизненным циклом;
- Course Builder: модули, темы, уроки и материалы;
- enrollment и Student Portal;
- прогресс обучения и календарь;
- Course History;
- PostgreSQL, Docker Compose, OpenAPI и Django Admin.

## Требования

- Python 3.12;
- PostgreSQL 14+;
- Git;
- Docker Desktop — только для запуска через Docker Compose.

Рекомендуется Python 3.12: он используется в Docker и CI. На Python 3.14 для
зафиксированной версии `psycopg2-binary` может отсутствовать готовый wheel, из-за
чего Windows потребует Microsoft C++ Build Tools.

## Быстрый локальный запуск

### 1. Репозиторий и виртуальное окружение

```powershell
git clone https://github.com/adilhanDevs/su-lms-backend.git
cd su-lms-backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Если команда `py` недоступна, используйте установленный Python 3.12 напрямую:

```powershell
python -m venv .venv
```

### 2. PostgreSQL

Создайте локального пользователя и базу данных через `psql` или pgAdmin. Не
используйте приведённый пароль вне локальной разработки.

```sql
CREATE USER su_lms_user WITH PASSWORD 'local-password';
CREATE DATABASE su_lms OWNER su_lms_user;
```

### 3. Переменные окружения

```powershell
Copy-Item .env.example .env
```

Минимально измените в `.env`:

```dotenv
DJANGO_DEBUG=True
SECRET_KEY=replace-with-a-local-random-value
DATABASE_URL=postgresql://su_lms_user:local-password@localhost:5432/su_lms
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173
CSRF_TRUSTED_ORIGINS=http://localhost:5173
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

`DATABASE_URL` имеет приоритет над отдельными переменными `DB_*`. Настройки
staging и production, реальные пароли, токены и ключи нельзя добавлять в
`.env.example` или коммитить в Git. Файл `.env` уже исключён через `.gitignore`.

### 4. Проверка, миграции и запуск

```powershell
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

После запуска доступны:

| Ресурс | URL |
|---|---|
| API v1 | `http://127.0.0.1:8000/api/v1/` |
| Health check | `http://127.0.0.1:8000/api/v1/health/` |
| Django Admin | `http://127.0.0.1:8000/admin/` |
| Swagger UI | `http://127.0.0.1:8000/api/docs/` |
| OpenAPI schema | `http://127.0.0.1:8000/api/schema/` |
| ReDoc | `http://127.0.0.1:8000/api/schema/redoc/` |

Проверка приложения и соединения с PostgreSQL:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/
```

Ожидаемый ответ:

```json
{
  "status": "ok",
  "database": "ok",
  "service": "su-lms-backend"
}
```

## Demo data

Идемпотентная команда заполняет роли, Organization, 9 курсов, Course Builder,
материалы, enrollments и календарь:

```powershell
python manage.py seed_release1
```

Повторный запуск обновляет принадлежащие seed-команде demo-данные и не создаёт
дубликаты.

| Роль | Login | Password |
|---|---|---|
| Super Admin | `superadmin@su.edu.kg` | `Demo123!` |
| LMS Admin | `admin@su.edu.kg` | `Demo123!` |
| Content Manager | `content@su.edu.kg` | `Demo123!` |
| Teacher | `teacher@su.edu.kg` | `Demo123!` |
| Teaching Assistant | `assistant@su.edu.kg` | `Demo123!` |
| Student | `student@su.edu.kg` | `Demo123!` |

Demo credentials предназначены только для development/demo environment. По
умолчанию команда отказывается работать при `DJANGO_DEBUG=False`. Локальный
пароль можно заменить:

```powershell
python manage.py seed_release1 --password "AnotherDemo123!"
```

## Основные API endpoints

```text
POST /api/v1/auth/login/
POST /api/v1/auth/refresh/
POST /api/v1/auth/logout/
GET  /api/v1/auth/me/

GET  /api/v1/courses/
POST /api/v1/courses/
GET  /api/v1/courses/{id}/
GET  /api/v1/courses/{id}/structure/
GET  /api/v1/courses/{id}/history/

GET  /api/v1/student/dashboard/
GET  /api/v1/student/courses/
GET  /api/v1/student/progress/
GET  /api/v1/student/calendar/
```

Полная карта экранов, permissions, payload и error codes находится в
[`docs/FRONTEND_API_CONTRACT.md`](docs/FRONTEND_API_CONTRACT.md). Актуальная
машиночитаемая спецификация генерируется через OpenAPI.

JWT выдаётся в `HttpOnly` cookies. Frontend должен отправлять cookies вместе с
запросами:

```javascript
fetch("http://127.0.0.1:8000/api/v1/auth/me/", {
  credentials: "include",
});
```

При использовании credentials origin не может быть `*`. Для локального
frontend уже предусмотрен `http://localhost:5173`; staging origins добавляются
через `CORS_ALLOWED_ORIGINS` и `CSRF_TRUSTED_ORIGINS` в окружении.

## Тесты и проверки

Полный набор Django-тестов использует настроенную PostgreSQL-базу и создаёт
отдельную тестовую базу:

```powershell
python manage.py test
```

Проверки, соответствующие CI:

```powershell
python manage.py check
python manage.py makemigrations accounts core attendance result finance organization courses enrollments learning progress audit --check --dry-run
python manage.py spectacular --file schema.yml --validate
python -m coverage run manage.py test
python -m coverage report
```

OpenAPI-команда создаёт локальный `schema.yml`; этот файл не нужно добавлять в
коммит, если изменение схемы не является отдельной задачей.

## Docker Compose

Docker Compose запускает `backend` и PostgreSQL 16:

```powershell
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:8000/api/v1/health/
```

Миграции применяются при запуске backend. Demo data создаётся отдельно:

```powershell
docker compose exec backend python manage.py seed_release1
```

По умолчанию:

- backend доступен на `http://localhost:8000`;
- PostgreSQL опубликован на host-порту `5433`;
- данные PostgreSQL и media сохраняются в Docker volumes.

Остановить сервисы без удаления volumes:

```powershell
docker compose down
```

## Структура Release 1

| App | Назначение |
|---|---|
| `accounts` | Пользователи, роли, permissions и JWT |
| `organization` | Faculty, Department, Program, Group и Semester |
| `courses` | Course, lifecycle, templates, copy и history API |
| `learning` | Modules, Topics, Lessons, Materials и SCORM |
| `enrollments` | Enrollment, Student Course API и SIS boundary |
| `progress` | Lesson Progress и Student Dashboard |
| `calendar_events` | Staff и Student Calendar |
| `audit` | Общие audit-поля и Course History events |

Старые apps сохранены для совместимости и не должны смешиваться с новыми
Release 1 моделями без отдельного плана миграции.

## Документация

- [Локальный запуск](docs/LOCAL_SETUP.md)
- [Архитектура](docs/ARCHITECTURE.md)
- [Frontend API contract](docs/FRONTEND_API_CONTRACT.md)
- [Audit model](docs/AUDIT_MODEL.md)
- [Backend audit](docs/BACKEND_AUDIT.md)

## Частые проблемы

### `psycopg2-binary` требует Microsoft Visual C++

Проверьте версию Python. Для проекта используйте Python 3.12 и пересоздайте
виртуальное окружение:

```powershell
deactivate
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### PostgreSQL connection refused

Убедитесь, что служба PostgreSQL запущена, база существует, а host, port и
credentials в `DATABASE_URL` соответствуют локальной конфигурации.

### Email недоступна

Оставьте console backend:

```dotenv
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

Письма будут выводиться в терминал, поэтому реальная почта для локальной
разработки не требуется.
