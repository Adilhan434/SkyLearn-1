# Развертывание Backend (SU LMS) на PythonAnywhere для sulmsbackend21

## Настройки для вашего аккаунта:
- **Username**: `sulmsbackend21`
- **Домен сайта**: `https://sulmsbackend21.pythonanywhere.com`

---

## 🚀 Пошаговая инструкция

### Шаг 1. Откройте Bash-консоль
1. Войдите в панель [pythonanywhere.com](https://www.pythonanywhere.com).
2. Перейдите во вкладку **Consoles** и нажмите **Bash**.

---

### Шаг 2. Загрузка кода и создание виртуального окружения
Вставьте и выполните в консоли:

```bash
# 1. Клонируйте репозиторий в папку su-lms-backend
git clone <URL_ВАШЕГО_РЕПОЗИТОРИЯ> su-lms-backend
cd su-lms-backend

# 2. Создайте виртуальное окружение с Python 3.10
python3.10 -m venv venv

# 3. Активируйте окружение
source venv/bin/activate

# 4. Установите все зависимости
pip install --upgrade pip
pip install -r requirements.txt
```

---

### Шаг 3. Применение миграций и сборка статики
В той же активной консоли выполните:

```bash
# Создание и применение базы данных SQLite
python manage.py migrate

# Сборка статических файлов для Swagger и Django Admin
python manage.py collectstatic --noinput
```

---

### Шаг 4. Настройка веб-приложения во вкладке "Web"
1. Перейдите во вкладку **Web** в верхнем меню PythonAnywhere.
2. Нажмите синюю кнопку **Add a new web app**:
   - Выберите **Manual configuration**
   - Выберите **Python 3.10**
3. Заполните поля в разделе **Code**:
   - **Source code**: `/home/sulmsbackend21/su-lms-backend`
   - **Working directory**: `/home/sulmsbackend21/su-lms-backend`
   - Кликните по ссылке **WSGI configuration file** (откроется файл `/var/www/sulmsbackend21_pythonanywhere_com_wsgi.py`).
   - Удалите всё, что там написано, и вставьте следующий готовый код:

```python
import os
import sys
from pathlib import Path

USERNAME = 'sulmsbackend21'
PROJECT_DIR_NAME = 'su-lms-backend'

project_home = f'/home/{USERNAME}/{PROJECT_DIR_NAME}'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

env_file = Path(project_home) / '.env'
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=env_file)
    except ImportError:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```
   - Нажмите зеленую кнопку **Save** в правом верхнем углу.

4. Заполните раздел **Virtualenv**:
   - Введите путь: `/home/sulmsbackend21/su-lms-backend/venv`
   - Нажмите галочку (Save).

5. В разделе **Static files** добавьте две строки:
   | URL | Directory |
   | :--- | :--- |
   | `/static/` | `/home/sulmsbackend21/su-lms-backend/staticfiles` |
   | `/media/` | `/home/sulmsbackend21/su-lms-backend/media` |

6. В самом верху страницы нажмите большую зеленую кнопку **Reload sulmsbackend21.pythonanywhere.com**.

---

## 📦 Добавление тестовых данных

В Bash-консоли (где активно окружение `(venv)`):

```bash
# 1. Загрузить полный набор демонстрационных данных
python manage.py seed_release1 --allow-production
```

### Созданные аккаунты для тестирования (пароль для всех: `Demo123!`):
- **Super Admin**: `superadmin@su.edu.kg` (Полный доступ к админке и API)
- **LMS Admin**: `admin@su.edu.kg`
- **Content Manager**: `content@su.edu.kg`
- **Teacher**: `teacher@su.edu.kg`
- **Assistant**: `assistant@su.edu.kg`
- **Student**: `student@su.edu.kg`

### Создать свой аккаунт суперпользователя (при желании):
```bash
python manage.py createsuperuser
```

---

## 🌐 Ваши ссылки после деплоя:

- 📘 **Swagger UI (Документация и тестирование API)**:  
  `https://sulmsbackend21.pythonanywhere.com/api/docs/`
- 📑 **Redoc (Документация)**:  
  `https://sulmsbackend21.pythonanywhere.com/api/schema/redoc/`
- 🛠 **Django Admin панель**:  
  `https://sulmsbackend21.pythonanywhere.com/admin/`
- 🔑 **Авторизация (JWT Login)**:  
  `POST https://sulmsbackend21.pythonanywhere.com/api/v1/auth/login/`  
  Body: `{"email": "superadmin@su.edu.kg", "password": "Demo123!"}`
