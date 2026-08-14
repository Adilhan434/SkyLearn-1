from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import (
    LMSPermission,
    LMSPermissionCode,
    Lecturer,
    Role,
    RoleCode,
    Student,
    User,
)


class SeedRelease1CommandTests(TestCase):
    def run_seed(self, **options):
        output = StringIO()
        options.setdefault("allow_production", True)
        call_command("seed_release1", stdout=output, **options)
        return output.getvalue()

    def test_command_creates_release1_roles_and_demo_users(self):
        output = self.run_seed()

        self.assertSetEqual(
            set(Role.objects.values_list("code", flat=True)),
            set(RoleCode.values),
        )
        self.assertSetEqual(
            set(
                User.objects.filter(
                    email__in=[
                        "superadmin@su.edu.kg",
                        "admin@su.edu.kg",
                        "teacher@su.edu.kg",
                        "student@su.edu.kg",
                    ]
                ).values_list("email", flat=True)
            ),
            {
                "superadmin@su.edu.kg",
                "admin@su.edu.kg",
                "teacher@su.edu.kg",
                "student@su.edu.kg",
            },
        )
        self.assertIn("Release 1 demo data is ready", output)
        self.assertSetEqual(
            set(LMSPermission.objects.values_list("code", flat=True)),
            set(LMSPermissionCode.values),
        )

    def test_demo_users_have_expected_roles_flags_and_password(self):
        self.run_seed()

        super_admin = User.objects.get(email="superadmin@su.edu.kg")
        lms_admin = User.objects.get(email="admin@su.edu.kg")
        teacher = User.objects.get(email="teacher@su.edu.kg")
        student = User.objects.get(email="student@su.edu.kg")

        self.assertSetEqual(
            set(super_admin.roles.values_list("code", flat=True)),
            {RoleCode.SUPER_ADMIN},
        )
        self.assertTrue(super_admin.is_superuser)
        self.assertTrue(super_admin.is_staff)
        self.assertSetEqual(
            set(lms_admin.roles.values_list("code", flat=True)),
            {RoleCode.LMS_ADMIN},
        )
        self.assertTrue(lms_admin.is_staff)
        self.assertTrue(teacher.is_lecturer)
        self.assertTrue(student.is_student)

        for user in [super_admin, lms_admin, teacher, student]:
            self.assertTrue(user.check_password("Demo123!"))

    def test_command_creates_teacher_and_student_profiles(self):
        self.run_seed()

        teacher = User.objects.get(email="teacher@su.edu.kg")
        student = User.objects.get(email="student@su.edu.kg")

        self.assertTrue(Lecturer.objects.filter(lecturer=teacher).exists())
        profile = Student.objects.get(student=student)
        self.assertEqual(profile.id_number, "SU-2024-0012")
        self.assertEqual(profile.group.name, "CS-22-24")
        self.assertEqual(profile.group.program.name, "Computer Science")

    def test_command_is_idempotent(self):
        self.run_seed()
        user_ids = list(
            User.objects.filter(email__endswith="@su.edu.kg")
            .order_by("email")
            .values_list("pk", flat=True)
        )
        counts = {
            "users": User.objects.count(),
            "roles": Role.objects.count(),
            "students": Student.objects.count(),
            "lecturers": Lecturer.objects.count(),
            "permissions": LMSPermission.objects.count(),
        }

        self.run_seed()

        self.assertEqual(
            list(
                User.objects.filter(email__endswith="@su.edu.kg")
                .order_by("email")
                .values_list("pk", flat=True)
            ),
            user_ids,
        )
        self.assertEqual(User.objects.count(), counts["users"])
        self.assertEqual(Role.objects.count(), counts["roles"])
        self.assertEqual(Student.objects.count(), counts["students"])
        self.assertEqual(Lecturer.objects.count(), counts["lecturers"])
        self.assertEqual(
            LMSPermission.objects.count(),
            counts["permissions"],
        )

    def test_command_restores_default_role_permissions(self):
        teacher_role = Role.objects.get(code=RoleCode.TEACHER)
        teacher_role.permissions.clear()

        self.run_seed()

        self.assertTrue(
            teacher_role.permissions.filter(code="courses.edit").exists()
        )
        self.assertFalse(
            teacher_role.permissions.filter(code="courses.publish").exists()
        )

    def test_custom_demo_password_is_supported(self):
        self.run_seed(password="DifferentDemo123!")

        self.assertTrue(
            User.objects.get(email="student@su.edu.kg").check_password(
                "DifferentDemo123!"
            )
        )

    @override_settings(DEBUG=False)
    def test_command_refuses_demo_data_in_production_by_default(self):
        with self.assertRaises(CommandError):
            self.run_seed(allow_production=False)

        self.assertFalse(
            User.objects.filter(email="student@su.edu.kg").exists()
        )
