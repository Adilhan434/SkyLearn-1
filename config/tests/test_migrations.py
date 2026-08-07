from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase


class MigrationStateTests(TestCase):
    release1_leaf_migrations = {
        ("accounts", "0009_add_student_id_number"),
        ("organization", "0001_initial"),
        ("courses", "0001_initial"),
    }

    def test_migration_graph_has_no_conflicts(self):
        executor = MigrationExecutor(connection)
        self.assertEqual(executor.loader.detect_conflicts(), {})

    def test_release1_leaf_migrations_are_applied(self):
        applied = MigrationRecorder(connection).applied_migrations()
        self.assertTrue(self.release1_leaf_migrations.issubset(applied))

    def test_database_is_at_current_project_leaf_migrations(self):
        executor = MigrationExecutor(connection)
        applied = MigrationRecorder(connection).applied_migrations()
        project_apps = {
            "accounts",
            "attendance",
            "core",
            "courses",
            "finance",
            "organization",
            "result",
        }
        expected_leaves = {
            node
            for node in executor.loader.graph.leaf_nodes()
            if node[0] in project_apps
        }

        self.assertTrue(expected_leaves.issubset(applied))
