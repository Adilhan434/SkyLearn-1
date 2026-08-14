from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import (
    Group,
    LMSPermission,
    LMSPermissionCode,
    Lecturer,
    Role,
    RoleCode,
    Student,
    User,
)
from accounts.permission_defaults import RELEASE1_ROLE_PERMISSIONS
from core.models import Program
from organization.models import (
    DegreeLevel,
    Department as OrganizationDepartment,
    Faculty,
    Group as OrganizationGroup,
    Program as OrganizationProgram,
    Semester,
)


DEMO_USERS = (
    {
        "email": "superadmin@su.edu.kg",
        "first_name": "Super",
        "last_name": "Admin",
        "role": RoleCode.SUPER_ADMIN,
        "is_staff": True,
    },
    {
        "email": "admin@su.edu.kg",
        "first_name": "LMS",
        "last_name": "Admin",
        "role": RoleCode.LMS_ADMIN,
        "is_staff": True,
    },
    {
        "email": "content@su.edu.kg",
        "first_name": "Content",
        "last_name": "Manager",
        "role": RoleCode.CONTENT_MANAGER,
        "is_staff": False,
    },
    {
        "email": "teacher@su.edu.kg",
        "first_name": "Teacher",
        "last_name": "Demo",
        "role": RoleCode.TEACHER,
        "is_staff": False,
    },
    {
        "email": "assistant@su.edu.kg",
        "first_name": "Teaching",
        "last_name": "Assistant",
        "role": RoleCode.TEACHING_ASSISTANT,
        "is_staff": False,
    },
    {
        "email": "student@su.edu.kg",
        "first_name": "Student",
        "last_name": "Demo",
        "role": RoleCode.STUDENT,
        "is_staff": False,
    },
)

FACULTIES = (
    ("ENG", "Faculty of Engineering"),
    ("BUS", "Faculty of Business and Economics"),
    ("HUM", "Faculty of Humanities and Social Sciences"),
)

DEPARTMENTS = (
    ("CS", "Computer Science", "ENG"),
    ("EE", "Electrical Engineering", "ENG"),
    ("BA", "Business Administration", "BUS"),
    ("ECON", "Economics", "BUS"),
    ("LANG", "Languages", "HUM"),
)

PROGRAMS = (
    ("SE", "Software Engineering", "CS", DegreeLevel.BACHELOR),
    ("CS-BSC", "Computer Science", "CS", DegreeLevel.BACHELOR),
    ("EE-BSC", "Electrical Engineering", "EE", DegreeLevel.BACHELOR),
    ("BBA", "Business Administration", "BA", DegreeLevel.BACHELOR),
    ("ECON-BSC", "Economics", "ECON", DegreeLevel.BACHELOR),
)

GROUPS = (
    ("SE-24", 2024, "SE"),
    ("CS-22", 2022, "CS-BSC"),
    ("EE-24", 2024, "EE-BSC"),
    ("BBA-23", 2023, "BBA"),
)

SEMESTERS = (
    ("Fall 2026", date(2026, 9, 1), date(2026, 12, 20)),
    ("Spring 2027", date(2027, 1, 25), date(2027, 5, 30)),
)


class Command(BaseCommand):
    help = "Create idempotent Release 1 demo users and organization data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="Demo123!",
            help="Password assigned to all demo accounts.",
        )
        parser.add_argument(
            "--allow-production",
            action="store_true",
            help="Explicitly allow demo data creation when DEBUG is false.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG and not options["allow_production"]:
            raise CommandError(
                "Refusing to create demo accounts while DEBUG is false. "
                "Use --allow-production only if this is intentional."
            )

        roles = self._ensure_roles()
        self._ensure_permissions(roles)
        users = {
            config["role"]: self._ensure_user(
                config,
                roles[config["role"]],
                options["password"],
            )
            for config in DEMO_USERS
        }
        self._ensure_profiles(users)
        self._ensure_organization(users[RoleCode.LMS_ADMIN])

        self.stdout.write(
            self.style.SUCCESS(
                "Release 1 demo data is ready: "
                "6 users, 6 roles, teacher and student profiles, "
                "3 faculties, 5 departments, 5 programs, 4 groups, "
                "and 2 semesters."
            )
        )

    def _ensure_roles(self):
        roles = {}
        for code, label in RoleCode.choices:
            role, _ = Role.objects.update_or_create(
                code=code,
                defaults={"name": str(label)},
            )
            roles[code] = role
        return roles

    def _ensure_permissions(self, roles):
        permissions = {}
        for code, label in LMSPermissionCode.choices:
            permission, _ = LMSPermission.objects.update_or_create(
                code=code,
                defaults={"name": str(label)},
            )
            permissions[code] = permission

        all_permissions = list(permissions.values())
        for role_code, permission_codes in RELEASE1_ROLE_PERMISSIONS.items():
            selected = (
                all_permissions
                if permission_codes == "*"
                else [permissions[code] for code in permission_codes]
            )
            roles[role_code].permissions.set(selected)

    def _ensure_user(self, config, role, password):
        matches = User.objects.filter(email__iexact=config["email"])
        if matches.count() > 1:
            raise CommandError(f"Multiple users use demo email {config['email']}.")

        user = matches.first()
        if user is None:
            user, _ = User.objects.get_or_create(
                username=config["email"],
                defaults={"email": config["email"]},
            )

        user.email = config["email"]
        user.first_name = config["first_name"]
        user.last_name = config["last_name"]
        user.is_active = True
        user.is_staff = config["is_staff"]
        user.set_password(password)
        user.save()
        user.roles.set([role])
        user.refresh_from_db()
        return user

    def _ensure_profiles(self, users):
        teacher = users[RoleCode.TEACHER]
        student = users[RoleCode.STUDENT]

        Lecturer.objects.update_or_create(
            lecturer=teacher,
            defaults={"admin": None},
        )

        program = Program.objects.filter(name="Computer Science").first()
        if program is None:
            program = Program.objects.create(name="Computer Science")

        group = Group.objects.filter(
            name="CS-22-24",
            program=program,
        ).first()
        if group is None:
            group = Group.objects.create(
                name="CS-22-24",
                program=program,
            )

        Student.objects.update_or_create(
            student=student,
            defaults={
                "id_number": "SU-2024-0012",
                "group": group,
                "admin": None,
            },
        )

    def _ensure_organization(self, actor):
        faculties = {}
        for code, name in FACULTIES:
            faculty, created = Faculty.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "is_active": True,
                    "updated_by": actor,
                },
            )
            if created:
                faculty.created_by = actor
                faculty.save(update_fields=("created_by",))
            faculties[code] = faculty

        departments = {}
        for code, name, faculty_code in DEPARTMENTS:
            department, created = OrganizationDepartment.objects.update_or_create(
                faculty=faculties[faculty_code],
                code=code,
                defaults={
                    "name": name,
                    "is_active": True,
                    "updated_by": actor,
                },
            )
            if created:
                department.created_by = actor
                department.save(update_fields=("created_by",))
            departments[code] = department

        programs = {}
        for code, name, department_code, degree_level in PROGRAMS:
            program, created = OrganizationProgram.objects.update_or_create(
                department=departments[department_code],
                code=code,
                defaults={
                    "name": name,
                    "degree_level": degree_level,
                    "is_active": True,
                    "updated_by": actor,
                },
            )
            if created:
                program.created_by = actor
                program.save(update_fields=("created_by",))
            programs[code] = program

        for name, admission_year, program_code in GROUPS:
            group, created = OrganizationGroup.objects.update_or_create(
                program=programs[program_code],
                name=name,
                admission_year=admission_year,
                defaults={
                    "is_active": True,
                    "updated_by": actor,
                },
            )
            if created:
                group.created_by = actor
                group.save(update_fields=("created_by",))

        for name, start_date, end_date in SEMESTERS:
            semester, created = Semester.objects.update_or_create(
                name=name,
                start_date=start_date,
                end_date=end_date,
                defaults={
                    "is_active": True,
                    "updated_by": actor,
                },
            )
            if created:
                semester.created_by = actor
                semester.save(update_fields=("created_by",))
