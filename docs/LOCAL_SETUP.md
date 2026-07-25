# Локальный запуск SU LMS Backend

## 1. Требования

Рекомендуемое окружение:

- Python 3.12;
- pip;
- Git;
- PostgreSQL 14+ — для режима, близкого к production;
- SQLite — доступен по умолчанию и подходит для быстрого локального запуска.

Проект может запускаться на других версиях Python, но основной локальной
версией следует считать Python 3.12.

## 2. Клонирование и виртуальное окружение

```powershell
git clone <repository-url>
cd su-lms-backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Для Linux или macOS активация выглядит так:

```bash
source .venv/bin/activate
```

Проверка версии:

```powershell
python --version
```

## 3. Установка зависимостей

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`requirements.txt` является единственным списком зависимостей проекта.

## 4. Настройка `.env`

Создайте локальный файл на основе примера:

```powershell
Copy-Item .env.example .env
```

`.env` исключён из Git. Не добавляйте в репозиторий реальные пароли, SMTP
credentials, production `SECRET_KEY` и другие секреты.

Минимальная конфигурация для SQLite:

```dotenv
DJANGO_DEBUG=True
SECRET_KEY="django-insecure-local-development-only"
DB_ENGINE=sqlite
EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"
```

При console email backend письма выводятся в терминал, поэтому доступ к
настоящей почте для локального запуска не нужен.

## 5. SQLite

SQLite используется по умолчанию:

```dotenv
DB_ENGINE=sqlite
```

Файл `db.sqlite3` будет создан в корне проекта после применения миграций. Он
является локальным и не отслеживается Git.

## 6. PostgreSQL

### Создание пользователя и базы

Откройте `psql` от имени администратора PostgreSQL:

```sql
CREATE USER su_lms_user WITH PASSWORD 'replace-with-local-password';
CREATE DATABASE su_lms OWNER su_lms_user;
```

Затем укажите в `.env`:

```dotenv
DB_ENGINE=postgresql
DB_NAME=su_lms
DB_USER=su_lms_user
DB_PASSWORD="replace-with-local-password"
DB_HOST=localhost
DB_PORT=5432
```

Для возврата на SQLite достаточно изменить:

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

Проверка отсутствия незаписанных изменений моделей:

```powershell
python manage.py makemigrations accounts core attendance finance result --check --dry-run
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

Это только локальные demo credentials. Не используйте этот пароль в
production.

Другой локальный пароль можно передать явно:

```powershell
python manage.py seed_release1 --password "AnotherDemo123!"
```

При `DJANGO_DEBUG=False` команда блокируется. Флаг `--allow-production`
существует только для явного контролируемого запуска и не должен применяться
на production-системах с реальными пользователями.

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
