from django.apps import apps
from django.test import SimpleTestCase


class LMSAppStructureTests(SimpleTestCase):
    release1_apps = {
        "organization": "LMS Organization",
        "courses": "LMS Courses",
        "enrollments": "LMS Enrollments",
        "learning": "LMS Learning",
        "progress": "LMS Progress",
        "audit": "LMS Audit",
    }

    def test_release1_domain_apps_are_registered(self):
        for app_label, verbose_name in self.release1_apps.items():
            with self.subTest(app=app_label):
                app_config = apps.get_app_config(app_label)
                self.assertEqual(app_config.verbose_name, verbose_name)

    def test_legacy_core_app_remains_registered(self):
        self.assertTrue(apps.is_installed("core"))

    def test_domain_boundaries_do_not_add_models_prematurely(self):
        reserved_apps = ("enrollments", "progress")
        for app_label in reserved_apps:
            with self.subTest(app=app_label):
                self.assertEqual(
                    list(apps.get_app_config(app_label).get_models()),
                    [],
                )

    def test_learning_contains_only_release1_structure_models(self):
        model_names = {
            model.__name__
            for model in apps.get_app_config("learning").get_models()
        }

        self.assertEqual(
            model_names,
            {"CourseModule", "CourseTopic", "Lesson"},
        )
