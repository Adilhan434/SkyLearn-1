from pathlib import Path

from django.test import SimpleTestCase

from config.database import build_database_config


def values_from(mapping):
    def get_value(key, default=None):
        return mapping.get(key, default)

    return get_value


class DatabaseConfigTests(SimpleTestCase):
    def test_sqlite_is_the_local_default(self):
        directory = Path("C:/project")
        database = build_database_config(
            directory,
            get_value=values_from({}),
        )

        self.assertEqual(database["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(
            database["NAME"],
            str(Path(directory) / "db.sqlite3"),
        )

    def test_postgresql_uses_environment_values(self):
        database = build_database_config(
            "/project",
            get_value=values_from(
                {
                    "DB_ENGINE": "postgresql",
                    "DB_NAME": "test_lms",
                    "DB_USER": "test_user",
                    "DB_PASSWORD": "test_password",
                    "DB_HOST": "database",
                    "DB_PORT": "5433",
                }
            ),
        )

        self.assertEqual(
            database,
            {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "test_lms",
                "USER": "test_user",
                "PASSWORD": "test_password",
                "HOST": "database",
                "PORT": "5433",
            },
        )

    def test_unsupported_engine_fails_with_clear_message(self):
        with self.assertRaisesMessage(ValueError, "Unsupported DB_ENGINE"):
            build_database_config(
                "/project",
                get_value=values_from({"DB_ENGINE": "mysql"}),
            )
