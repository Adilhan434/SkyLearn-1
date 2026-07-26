# Аудит backend SU LMS

Дата аудита: 25 июля 2026  
Ветка: `feature/auth-users-foundation`

## 1. Цель и границы аудита

Аудит фиксирует текущее состояние backend перед созданием Release 1 API:

- versioned namespace `/api/v1/`;
- JWT login, refresh, logout и current user;
- базовая модель ролей;
- минимальный User API;
- единый формат ошибок;
- OpenAPI/Swagger;
- seed-команда и локальная документация.

Аудит не изменяет существующие бизнес-модули и не предлагает удалять старые
маршруты в рамках Release 1.

## 2. Текущее техническое состояние

- Framework: Django 4.2.20.
- API: Django REST Framework 3.16.1.
- Аутентификация: SimpleJWT 5.5.1.
- OpenAPI: drf-spectacular 0.29.0.
- Текущая локальная БД: SQLite.
- Custom user model: `accounts.User`.
- Глобальное правило DRF: запросы требуют аутентификацию, если view явно не
  задаёт другое permission.
- Локальный запуск, миграции и Django system check работают.
- Основной список зависимостей: `requirements.txt`.

## 3. Django apps

| App | Назначение | Основные модели | Release 1 | Что изменить | Риски |
|---|---|---|---|---|---|
| `accounts` | Пользователи, профили, группы, старая JWT-авторизация | `User`, `Lecturer`, `Student`, `Parent`, `Group` | Да | Добавить новый versioned auth/users/roles API, `Role`, `UserRole`, миграцию данных и тесты | App перегружен; роли представлены boolean-флагами; email не обязательный и не уникальный |
| `core` | Учебная структура, курсы, распределения и уведомления | `Course`, `CourseAllocation`, `Program`, `AcademicYear`, `Semester`, `Module`, `Notification` | Частично | В Release 1 переиспользовать только связи, необходимые для профиля; старый API сохранить | Смешаны разные области; часть detail endpoints не имеет явного admin permission |
| `attendance` | Расписание занятий и посещаемость | `LessonTime`, `ScheduleItem`, `Attendance` | Нет | Не менять в Release 1; проверить совместимость со старыми role-флагами | Опечатки в именах полей `Student` и `shcedule`; permissions завязаны на boolean-роли |
| `result` | Оценки по модулям и семестру | `Grade_1st_module`, `Grade_2nd_module`, `Grade_semester` | Нет | Не менять в Release 1 | Нестандартные имена моделей; сложные viewsets; доступ зависит от старых ролей и связей профилей |
| `finance` | Счета, платежи и договоры | `Invoice`, `Payment`, `Contract` | Нет | Не менять в Release 1 | Несколько view-классов определены дважды; последнее определение скрывает предыдущее |

### Сторонние apps

- `jet` и `jet.dashboard` — оформление Django Admin.
- `django_filters` — фильтрация списков.
- `rest_framework` и `rest_framework.authtoken` — API и legacy token app.
- `rest_framework_simplejwt` — JWT.
- `corsheaders` — CORS.
- `drf_spectacular` — OpenAPI.
- `crispy_forms` — формы старой Django-части.
- `django_browser_reload` — добавляется только в debug-режиме.

## 4. Модели, пригодные для повторного использования

### `accounts.User`

Можно сохранить как основную модель пользователя. Уже содержит:

- стандартные поля `AbstractUser`;
- имя, фамилию и email;
- активность и Django permissions;
- контактные данные;
- legacy-флаги `is_student`, `is_lecturer`, `is_parent`, `is_dep_head`,
  `is_accountant`.

Необходимые изменения:

- добавить связь с новой моделью ролей;
- не удалять legacy-флаги в Release 1;
- согласовать уникальность и обязательность email;
- не раскрывать служебные и role-флаги в новом публичном serializer;
- использовать стабильный serializer для `/api/v1/auth/me/`.

Риск: текущий login SimpleJWT ориентирован на `username`, а новый контракт
принимает поле `login` с email.

### Профили

- `Student` можно использовать для student profile.
- `Lecturer` можно использовать для teacher profile.
- `Group` и связанный `Program` можно использовать для группы студента.
- `Parent` относится к будущему parent release и не входит в Release 1.

В текущем `Student` отсутствует поле `student_id`, требуемое примером ответа
`/auth/me/`. Нужно согласовать добавление поля или временно возвращать `null`.

### Учебная структура

`Program`, `AcademicYear`, `Semester`, `Module`, `Course` и
`CourseAllocation` пригодны как начальная LMS-модель. Полный Course Management
не входит в Release 1, поэтому их схему сейчас менять не требуется.

## 5. Текущая авторизация

Доступны legacy endpoints:

| Метод | Endpoint | Назначение |
|---|---|---|
| POST | `/accounts/token/` | Получение access/refresh JWT и установка cookies |
| POST | `/accounts/token/refresh/` | Обновление access token из refresh cookie |
| GET | `/accounts/profile/` | Профиль текущего пользователя |

Положительные стороны:

- access token читается из httpOnly cookie;
- Authorization header сохранён как fallback;
- login и refresh доступны без предварительной аутентификации;
- profile требует аутентификацию.

Проблемы относительно Release 1:

- отсутствует `/api/v1/auth/`;
- отсутствует logout;
- login принимает стандартный `username`, а не контракт `login`;
- login возвращает JWT в JSON даже при установке cookies;
- login печатает входные данные запроса при ошибке, что может раскрыть пароль
  в логах;
- ошибки не соответствуют единому формату;
- profile возвращает legacy boolean-флаги вместо списка ролей;
- refresh rotation реализована вручную, но blacklist app не подключён;
- access token настроен на пять дней;
- отсутствуют контрактные API-тесты login/refresh/logout/me.

Рекомендация: сохранить legacy endpoints, а Release 1 auth реализовать
отдельным versioned API с собственными serializers, views и тестами.

## 6. Текущие API endpoints

### `accounts`

- `/accounts/token/`
- `/accounts/token/refresh/`
- `/accounts/profile/`
- `/accounts/lecturers/`
- `/accounts/lecturers/create/`
- `/accounts/lecturers/{id}/`
- `/accounts/lecturers/update/{id}/`
- `/accounts/students/`
- `/accounts/students/create/`
- `/accounts/students/{id}/`
- `/accounts/students/update/{id}/`
- `/accounts/students/by-group/{group_id}/`
- `/accounts/groups/`
- `/accounts/groups/create/`
- `/accounts/groups/{id}/`
- `/accounts/groups/update/{id}/`
- `/accounts/parents/`
- `/accounts/parents/create/`
- `/accounts/parents/{id}/`
- `/accounts/parents/update/{id}/`

### `core`

- `/api/programs/`
- `/api/academic-years/`
- `/api/semesters/`
- `/api/modules/`
- `/api/courses/`
- `/api/course-allocations/`
- `/api/teacher-allocations/`
- `/api/course-allocations/group/{group_id}/`
- `/api/notifications/`

Для большинства сущностей дополнительно существуют create, update и detail
routes.

### `attendance`

Router под `/attendance/`:

- `lesson-times`;
- `schedules`;
- `attendances`;
- дополнительные ViewSet actions.

### `result`

Router под `/result/api/`:

- `grade-1st-modules`;
- `grade-2nd-modules`;
- `grade-semesters`;
- `lecturer/bulk-grades`;
- `lecturer/course-grades`.

### `finance`

Под `/finance/` доступны API счетов, платежей, баланса, student/parent кабинета
и accountant operations.

### OpenAPI

- `/api/schema/`
- `/api/schema/swagger-ui/`
- `/api/schema/redoc/`

Для ТЗ рекомендуется сохранить schema endpoint и добавить короткий
`/api/docs/`, не ломая текущий Swagger URL.

## 7. Permissions и роли

Текущая авторизация использует:

- Django `is_superuser`, `is_staff`;
- boolean-флаги `is_student`, `is_lecturer`, `is_parent`, `is_accountant`;
- отдельные permission-классы в приложениях;
- legacy decorators для старых template views.

Проблемы:

- нет `Role` и `UserRole`;
- один пользователь формально может иметь несколько true-флагов, но это не
  оформлено как доменная модель;
- одинаковые проверки ролей дублируются между apps;
- `IsAdminUser` проверяет `is_staff`, а не будущие роли `lms_admin` и
  `super_admin`;
- нет единого permission для нового User API.

Минимальные роли Release 1:

- `student`;
- `teacher`;
- `teaching_assistant`;
- `content_manager`;
- `lms_admin`;
- `super_admin`.

Рекомендуемая миграция legacy-данных:

- `is_student=True` → `student`;
- `is_lecturer=True` → `teacher`;
- `is_superuser=True` → `super_admin`;
- остальные старые флаги пока сохранить без удаления.

Сопоставление `is_staff` с `lms_admin` нельзя выполнять автоматически без
проверки существующих пользователей.

## 8. Django templates

В проекте найдены только email templates:

- `templates/accounts/email/new_student_account_confirmation.html`;
- `templates/accounts/email/new_parent_account_confirmation.html`;
- `templates/accounts/email/new_lecturer_account_confirmation.html`.

Они используются email-утилитами и не мешают API-first архитектуре. Переносить
или удалять их в Release 1 не требуется.

## 9. Конфигурация и инфраструктурные риски

- Локально используется SQLite, а ТЗ требует документировать PostgreSQL.
- `SECRET_KEY` имеет небезопасное default-значение в settings.
- `ALLOWED_HOSTS` захардкожен.
- `CommonMiddleware` добавлен дважды.
- `TAILWIND_APP_NAME = "theme"` задан, но app `theme` отсутствует.
- `Procfile.tailwind` выглядит неиспользуемым.
- Python 3.14 требует monkey patch для Django templates; для воспроизводимого
  окружения лучше зафиксировать поддерживаемую версию Python.
- В `core` serializers широко используется `fields = "__all__"`, что может
  непреднамеренно раскрывать внутренние поля.
- В `accounts` создание профилей выполняет отправку email внутри serializer;
  ошибка внешнего сервиса может повлиять на создание пользователя.
- Временные диагностические скрипты используют конкретные usernames и слабые
  demo passwords; они перенесены в `scripts/`, но не должны использоваться в
  production.

## 10. Риски доступа в существующем API

Следующие места требуют отдельной проверки безопасности:

- `core` retrieve/destroy/update views не всегда задают явный
  `IsAdminUser`;
- `CourseRetrieveUpdateDestroyAPIView` допускает update/delete под глобальным
  `IsAuthenticated`;
- `CourseAllocationRetrieveUpdateDestroyAPIView` имеет ту же проблему;
- некоторые list/detail endpoints возвращают данные всем авторизованным
  пользователям без фильтрации по организации;
- finance содержит повторные определения классов views;
- permissions всех будущих модулей завязаны на legacy-флаги.

Эти проблемы не следует исправлять одновременно с auth foundation без
отдельных тестов, поскольку старый frontend может зависеть от текущего
поведения.

## 11. Предлагаемая структура Release 1

```text
api/
    __init__.py
    v1/
        __init__.py
        urls.py

accounts/
    api/
        __init__.py
        v1/
            __init__.py
            urls.py
            auth_views.py
            user_views.py
            serializers.py
            permissions.py
            exception_handler.py
```

Новые маршруты:

```text
/api/v1/auth/login/
/api/v1/auth/logout/
/api/v1/auth/refresh/
/api/v1/auth/me/
/api/v1/users/
/api/v1/users/{id}/
/api/v1/roles/
```

Старые маршруты продолжают работать до отдельного этапа deprecation.

## 12. Рекомендуемый порядок Release 1

1. Создать каркас `/api/v1/` без изменения старых URLs.
2. Добавить `Role`, `UserRole`, admin и миграции.
3. Добавить data migration legacy-флагов.
4. Реализовать и протестировать login/refresh/logout/me.
5. Реализовать и протестировать User API и permissions.
6. Добавить единый exception handler и тесты ошибок.
7. Обновить OpenAPI и добавить `/api/docs/`.
8. Добавить идемпотентную `seed_release1`.
9. Подготовить `docs/LOCAL_SETUP.md`.
10. Проверить миграции на чистой и существующей базе.

## 13. Правило тестирования новых функций

Начиная с Release 1, новая функциональность считается готовой только вместе с
автоматическими тестами.

Минимально проверяются:

- успешный сценарий;
- validation errors;
- запрос без аутентификации;
- недостаточная роль;
- отсутствие объекта;
- побочные эффекты в БД и cookies;
- совместимость старых endpoints, если меняется общий код.

Для auth дополнительно проверяются active/inactive user, срок и тип токена,
refresh rotation, logout и удаление cookies. Для seed-команд — повторный запуск
без дубликатов.

## 14. Итог

Существующий backend можно использовать как основу Release 1 без переписывания
с нуля. Модели пользователей, профилей, групп и учебной структуры пригодны для
повторного использования.

Главная стратегия: строить новый versioned API рядом со старым, постепенно
перевести авторизацию и роли на стабильный контракт, покрывать каждую новую
функцию тестами и не удалять legacy-код до подтверждения совместимости с
frontend.

## 15. Статус аудита на 26 июля 2026

Проверка foundation-части Release 1 подтверждена автоматическими тестами:

- `python manage.py test api.tests accounts.tests`;
- найдено и успешно выполнено 82 теста;
- итог тестового запуска — `OK`;
- сообщения `ERROR` и `WARNING` внутри вывода относятся к намеренно
  проверяемым ответам 500, 400, 401, 403, 404 и 405 и не означают падение
  тестового набора.

Новые auth, user, role, error-formatting и API versioning сценарии покрыты
тестами. Требование о тестах для новой функциональности соблюдается.

## 16. Проверка репозитория на секреты

Статус: **НЕ ПРОЙДЕНО — требуется устранить одно блокирующее замечание**.

Проверены отслеживаемые файлы рабочей версии по сигнатурам приватных ключей,
API-токенов, облачных ключей и явных присваиваний паролей. Дополнительно
проверены чувствительные имена файлов в истории Git и конфигурационные значения
без вывода самих секретов.

### Блокирующие замечания

1. `db.sqlite3.backup` отслеживается Git и присутствует как минимум в двух
   коммитах истории. В базе обнаружены таблицы пользователей и токенов. Такой
   файл может содержать password hashes, персональные данные и токены, поэтому
   его нельзя хранить в репозитории. Простого удаления из текущей ветки
   недостаточно, если репозиторий уже публиковался: потребуется отдельно
   согласованная очистка истории и ротация потенциально раскрытых данных.
### Предупреждение

- `scripts/reset_mama.py` и `scripts/reset_pass.py` устанавливают слабый
  пароль `123`. Это не найденный production-секрет, но такие вспомогательные
  скрипты небезопасны: пароль нужно принимать через защищённый интерактивный
  ввод или environment и не фиксировать в исходном коде.

### Допустимые значения

- значения в `.env.example` и `.github/workflows/django.yml` распознаны как
  placeholders;
- `Demo123!` используется только для локального demo seed и документации;
- `Temporary123!` и аналогичные значения находятся в автоматических тестах;
- `.env` отсутствует и игнорируется Git;
- рабочий `db.sqlite3` игнорируется Git.

### Что не обнаружено

В текущей отслеживаемой версии не обнаружены сигнатуры приватных ключей,
GitHub/OpenAI/Slack tokens и AWS access keys.

Постоянное fallback-значение `SECRET_KEY` удалено из `config/settings.py`.
Теперь ключ обязателен и загружается из environment или локального `.env`,
который игнорируется Git.

Проверка выполнена встроенным поиском по сигнатурам: `gitleaks` и
`trufflehog` в локальном окружении не установлены. Поэтому после устранения
блокеров перед публикацией рекомендуется дополнительно прогнать
специализированный scanner по всей истории Git.

### Definition of Done

- автоматические тесты foundation API: **пройдено**;
- отсутствие секретов и чувствительных данных в Git: **не пройдено**;
- audit report: **обновлён**;
- pull request в `develop`: **не подтверждён в рамках этого аудита**.
