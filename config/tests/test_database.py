from pathlib import Path

from unittest import TestCase as SimpleTestCase

from config.database import build_database_config


def values_from(mapping):
    def get_value(key, default=None):
        return mapping.get(key, default)

    return get_value


class DatabaseConfigTests(SimpleTestCase):
    def test_database_url_configures_postgresql(self):
        database = build_database_config(
            "/project",
            get_value=values_from(
                {
                    "DATABASE_URL": (
                        "postgresql://test_user:test%20password@database:5433/test_lms"
                    ),
                    "DB_ENGINE": "sqlite",
                }
            ),
        )

        self.assertEqual(
            database,
            {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "test_lms",
                "USER": "test_user",
                "PASSWORD": "test password",
                "HOST": "database",
                "PORT": "5433",
            },
        )

    def test_invalid_database_url_scheme_fails_clearly(self):
        with self.assertRaisesRegex(ValueError, "DATABASE_URL scheme"):
            build_database_config(
                "/project",
                get_value=values_from(
                    {"DATABASE_URL": "oracle://user:password@database/app"}
                ),
            )

    def test_sqlite_is_the_default(self):
        directory = Path("/project")
        database = build_database_config(
            directory,
            get_value=values_from({}),
        )

        self.assertEqual(database["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(
            database["NAME"],
            str(Path(directory) / "db.sqlite3"),
        )

    def test_database_url_configures_sqlite(self):
        directory = Path("/project")
        database = build_database_config(
            directory,
            get_value=values_from({"DATABASE_URL": "sqlite:///custom_db.sqlite3"}),
        )

        self.assertEqual(database["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(
            database["NAME"],
            str(Path(directory) / "custom_db.sqlite3"),
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

    def test_mysql_uses_environment_values(self):
        database = build_database_config(
            "/project",
            get_value=values_from(
                {
                    "DB_ENGINE": "mysql",
                    "DB_NAME": "test_lms",
                    "DB_USER": "test_user",
                    "DB_PASSWORD": "test_password",
                    "DB_HOST": "mysql.server",
                    "DB_PORT": "3306",
                }
            ),
        )

        self.assertEqual(
            database,
            {
                "ENGINE": "django.db.backends.mysql",
                "NAME": "test_lms",
                "USER": "test_user",
                "PASSWORD": "test_password",
                "HOST": "mysql.server",
                "PORT": "3306",
            },
        )

    def test_unsupported_engine_fails_with_clear_message(self):
        with self.assertRaisesRegex(ValueError, "Unsupported DB_ENGINE"):
            build_database_config(
                "/project",
                get_value=values_from({"DB_ENGINE": "oracle"}),
            )
