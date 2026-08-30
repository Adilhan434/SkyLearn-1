from pathlib import Path
from urllib.parse import unquote, urlparse

from decouple import config


def build_database_config(base_dir, get_value=config):
    database_url = get_value("DATABASE_URL", default="").strip()
    if database_url:
        parsed = urlparse(database_url)
        if parsed.scheme == "sqlite":
            db_path = parsed.path.lstrip("/")
            return {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(Path(base_dir) / db_path) if db_path else str(Path(base_dir) / "db.sqlite3"),
            }
        if parsed.scheme == "mysql":
            if not parsed.path.lstrip("/"):
                raise ValueError("DATABASE_URL must include a database name.")
            return {
                "ENGINE": "django.db.backends.mysql",
                "NAME": unquote(parsed.path.lstrip("/")),
                "USER": unquote(parsed.username or ""),
                "PASSWORD": unquote(parsed.password or ""),
                "HOST": parsed.hostname or "localhost",
                "PORT": str(parsed.port or 3306),
            }
        if parsed.scheme not in {"postgres", "postgresql"}:
            raise ValueError(
                "Unsupported DATABASE_URL scheme. Use 'sqlite', 'postgresql', or 'mysql'."
            )
        if not parsed.path.lstrip("/"):
            raise ValueError("DATABASE_URL must include a database name.")

        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "localhost",
            "PORT": str(parsed.port or 5432),
        }

    engine = get_value("DB_ENGINE", default="sqlite").strip().lower()

    if engine == "sqlite":
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(Path(base_dir) / "db.sqlite3"),
        }

    if engine in {"postgres", "postgresql"}:
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": get_value("DB_NAME", default="su_lms"),
            "USER": get_value("DB_USER", default="su_lms_user"),
            "PASSWORD": get_value("DB_PASSWORD", default=""),
            "HOST": get_value("DB_HOST", default="localhost"),
            "PORT": get_value("DB_PORT", default="5432"),
        }

    if engine == "mysql":
        return {
            "ENGINE": "django.db.backends.mysql",
            "NAME": get_value("DB_NAME", default="su_lms"),
            "USER": get_value("DB_USER", default="root"),
            "PASSWORD": get_value("DB_PASSWORD", default=""),
            "HOST": get_value("DB_HOST", default="localhost"),
            "PORT": get_value("DB_PORT", default="3306"),
        }

    raise ValueError(
        "Unsupported DB_ENGINE. Use 'sqlite', 'postgres', 'postgresql', or 'mysql'."
    )
