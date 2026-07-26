"""Initialize Django for scripts executed outside manage.py."""

import os
import sys
from pathlib import Path


def setup_django():
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django

    django.setup()
