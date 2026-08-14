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
from organization.models import Department, Faculty
from organization.models import Group as OrganizationGroup
from organization.models import Program as OrganizationProgram
from organization.models import Semester


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
                        "content@su.edu.kg",
                        "teacher@su.edu.kg",
                        "assistant@su.edu.kg",
                        "student@su.edu.kg",
                    ]
                ).values_list("email", flat=True)
            ),
            {
                "superadmin@su.edu.kg",
                "admin@su.edu.kg",
                "content@su.edu.kg",
                "teacher@su.edu.kg",
                "assistant@su.edu.kg",
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
        content_manager = User.objects.get(email="content@su.edu.kg")
        teacher = User.objects.get(email="teacher@su.edu.kg")
        teaching_assistant = User.objects.get(email="assistant@su.edu.kg")
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
        self.assertSetEqual(
            set(content_manager.roles.values_list("code", flat=True)),
            {RoleCode.CONTENT_MANAGER},
        )
        self.assertSetEqual(
            set(teaching_assistant.roles.values_list("code", flat=True)),
            {RoleCode.TEACHING_ASSISTANT},
        )
        self.assertTrue(lms_admin.is_staff)
        self.assertTrue(teacher.is_lecturer)
        self.assertTrue(student.is_student)

        for user in [
            super_admin,
            lms_admin,
            content_manager,
            teacher,
            teaching_assistant,
            student,
        ]:
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

    def test_command_creates_release1_organization_demo_data(self):
        self.run_seed()

        self.assertSetEqual(
            set(Faculty.objects.values_list("code", flat=True)),
            {"ENG", "BUS", "HUM"},
        )
        self.assertEqual(
            Department.objects.filter(
                code__in={"CS", "EE", "BA", "ECON", "LANG"}
            ).count(),
            5,
        )
        self.assertEqual(
            OrganizationProgram.objects.filter(
                code__in={"SE", "CS-BSC", "EE-BSC", "BBA", "ECON-BSC"}
            ).count(),
            5,
        )
        self.assertEqual(
            OrganizationGroup.objects.filter(
                name__in={"SE-24", "CS-22", "EE-24", "BBA-23"}
            ).count(),
            4,
        )
        self.assertSetEqual(
            set(Semester.objects.values_list("name", flat=True)),
            {"Fall 2026", "Spring 2027"},
        )

        computer_science = Department.objects.get(code="CS")
        software_engineering = OrganizationProgram.objects.get(code="SE")
        self.assertEqual(computer_science.faculty.code, "ENG")
        self.assertEqual(
            software_engineering.department,
            computer_science,
        )
        self.assertEqual(software_engineering.degree_level, "bachelor")
        self.assertTrue(
            Faculty.objects.filter(
                created_by__email="admin@su.edu.kg",
                updated_by__email="admin@su.edu.kg",
            ).exists()
        )

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
            "faculties": Faculty.objects.count(),
            "departments": Department.objects.count(),
            "organization_programs": OrganizationProgram.objects.count(),
            "organization_groups": OrganizationGroup.objects.count(),
            "semesters": Semester.objects.count(),
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
        self.assertEqual(Faculty.objects.count(), counts["faculties"])
        self.assertEqual(Department.objects.count(), counts["departments"])
        self.assertEqual(
            OrganizationProgram.objects.count(),
            counts["organization_programs"],
        )
        self.assertEqual(
            OrganizationGroup.objects.count(),
            counts["organization_groups"],
        )
        self.assertEqual(Semester.objects.count(), counts["semesters"])

    def test_command_restores_default_role_permissions(self):
        teacher_role = Role.objects.get(code=RoleCode.TEACHER)
        teacher_role.permissions.clear()

        self.run_seed()

        self.assertTrue(teacher_role.permissions.filter(code="courses.edit").exists())
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

        self.assertFalse(User.objects.filter(email="student@su.edu.kg").exists())
