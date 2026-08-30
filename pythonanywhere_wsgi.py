# ==============================================================================
# PythonAnywhere WSGI Configuration Template
# ==============================================================================
# Скопируйте содержимое этого файла в файл WSGI конфигурации на PythonAnywhere:
# /var/www/<your_username>_pythonanywhere_com_wsgi.py
# (ссылка на него находится во вкладке "Web" -> раздел "Code" -> "WSGI configuration file")
# ==============================================================================

import os
import sys
from pathlib import Path

# 1. Логин на PythonAnywhere:
USERNAME = 'sulmsbackend21'
PROJECT_DIR_NAME = 'su-lms-backend'

# 2. Путь к директории проекта
project_home = f'/home/{USERNAME}/{PROJECT_DIR_NAME}'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 3. Загрузка переменных окружения из .env (если файл .env создан)
env_file = Path(project_home) / '.env'
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=env_file)
    except ImportError:
        pass

# 4. Установка модуля настроек Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# 5. Инициализация WSGI приложения Django
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
