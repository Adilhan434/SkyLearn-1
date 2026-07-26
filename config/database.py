from pathlib import Path

from decouple import config


def build_database_config(base_dir, get_value=config):
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

    raise ValueError(
        "Unsupported DB_ENGINE. Use 'sqlite', 'postgres', or 'postgresql'."
    )
