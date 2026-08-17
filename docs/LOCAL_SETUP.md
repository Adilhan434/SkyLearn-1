# Локальный запуск SU LMS Backend

## 1. Требования

- Python 3.12;
- pip;
- Git;
- PostgreSQL 14+;
- SQLite — только для отдельных изолированных тестов.

## 2. Клонирование и виртуальное окружение

```powershell
git clone <repository-url>
cd su-lms-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```


## 3. Установка зависимостей

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 4. Настройка `.env`


```powershell
Copy-Item .env.example .env
```

Минимальная dev-конфигурация:

```dotenv
DJANGO_DEBUG=True
SECRET_KEY="change-me-use-at-least-50-random-characters-for-this-value"
DATABASE_URL=postgresql://postgres:replace-with-local-password@localhost:5432/su_lms
EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"
```

При console email backend письма выводятся в терминал, поэтому доступ к
настоящей почте для локального запуска не нужен.

## 5. PostgreSQL

PostgreSQL используется как основная dev-база. `DATABASE_URL` имеет
приоритет над отдельными `DB_*` variables.

### Создание пользователя и базы

 `psql` от имени администратора PostgreSQL:

```sql
CREATE USER su_lms_user WITH PASSWORD 'replace-with-local-password';
CREATE DATABASE su_lms OWNER su_lms_user;
```

В `.env`:

```dotenv
DATABASE_URL=postgresql://su_lms_user:replace-with-local-password@localhost:5432/su_lms
```

## 6. SQLite для изолированных тестов

Чтобы явно выбрать SQLite, удалите `DATABASE_URL` из environment и укажите:

```dotenv
DB_ENGINE=sqlite
```

SQLite и PostgreSQL используют разные базы. После переключения необходимо
повторно применить миграции и seed-команду.

## 7. Миграции

Проверка проекта:

```powershell
python manage.py check
```

Применение миграций:

```powershell
python manage.py migrate
```

## 8. Demo seed

Создание ролей, demo-пользователей и базовых профилей:

```powershell
python manage.py seed_release1
```

Команда идемпотентна: её можно запускать повторно без создания дубликатов.

Demo credentials:

| Роль | Login | Password |
|---|---|---|
| Super Admin | `superadmin@su.edu.kg` | `Demo123!` |
| LMS Admin | `admin@su.edu.kg` | `Demo123!` |
| Teacher | `teacher@su.edu.kg` | `Demo123!` |
| Student | `student@su.edu.kg` | `Demo123!` |


Другой локальный пароль можно передать явно:

```powershell
python manage.py seed_release1 --password "AnotherDemo123!"
```


## 9. Запуск сервера

```powershell
python manage.py runserver
```

По умолчанию backend доступен по адресу:

```text
http://127.0.0.1:8000/
```

API version 1:

```text
http://127.0.0.1:8000/api/v1/
```

## 10. Swagger и OpenAPI

- Swagger UI: `http://127.0.0.1:8000/api/docs/`
- OpenAPI schema: `http://127.0.0.1:8000/api/schema/`
- ReDoc: `http://127.0.0.1:8000/api/schema/redoc/`

Документация Release 1 содержит только versioned endpoints `/api/v1/`.

JWT хранится в httpOnly cookies. Для запросов из frontend необходимо включать
credentials:

```javascript
fetch("http://127.0.0.1:8000/api/v1/auth/me/", {
  credentials: "include"
});
```

## 11. Основные Release 1 endpoints

```text
POST /api/v1/auth/login/
POST /api/v1/auth/logout/
POST /api/v1/auth/refresh/
GET  /api/v1/auth/me/

GET  /api/v1/users/
POST /api/v1/users/
GET  /api/v1/users/{id}/

GET  /api/v1/roles/
```

## 12. Тесты

Запуск тестов Release 1:

```powershell
python manage.py test api.tests accounts.tests
```

Запуск всех обнаруживаемых Django tests:

```powershell
python manage.py test
```

Перед Pull Request рекомендуется выполнить:

```powershell
python manage.py check
python manage.py makemigrations accounts core attendance finance result --check --dry-run
python manage.py test api.tests accounts.tests
python manage.py spectacular --file schema.yml --validate
```

## 13. Частые проблемы

### `DEBUG=release` или другое некорректное значение

Проект использует переменную `DJANGO_DEBUG`, а не общую системную переменную
`DEBUG`. Допустимые значения:

```text
True / False
1 / 0
yes / no
```

### PostgreSQL connection refused

Проверьте, что служба PostgreSQL запущена, а `DB_HOST` и `DB_PORT` в `.env`
соответствуют локальной установке.

### Ошибки после переключения базы

Примените миграции и seed к новой базе:

```powershell
python manage.py migrate
python manage.py seed_release1
```

### Не отправляется email

Для локальной разработки оставьте:

```dotenv
EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"
```

Письма будут отображаться в терминале.

### Production security flags

После настройки HTTPS в production задайте `SECURE_SSL_REDIRECT=True`,
`SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True` и подходящее значение
`SECURE_HSTS_SECONDS`. Параметры `SECURE_HSTS_INCLUDE_SUBDOMAINS` и
`SECURE_HSTS_PRELOAD` включайте только после проверки HTTPS на всех поддоменах.
Для локальной HTTP-разработки эти флаги должны оставаться выключенными.

## 14. Опциональный запуск через Docker

Основным способом разработки остаётся локальный Python 3.12 и PostgreSQL.
Docker Compose предоставляет дополнительное изолированное окружение с
сервисами `backend` и `postgres`.

Запуск:

```powershell
docker compose up --build
```

Backend будет доступен по адресу `http://localhost:8000`, frontend origin —
`http://localhost:5173`, PostgreSQL публикуется на host-порту `5433`, чтобы не
конфликтовать с локальным PostgreSQL на стандартном порту `5432`.

Проверка:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health/
docker compose ps
```

Остановка без удаления данных PostgreSQL:

```powershell
docker compose down
```

Локальный `.env` не копируется в Docker image. Для изменения Docker-настроек
используйте environment variables `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_PORT` и `BACKEND_PORT`. Значения по умолчанию
предназначены только для локальной разработки.
