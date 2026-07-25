from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import (
    Group,
    Lecturer,
    Role,
    RoleCode,
    Student,
    User,
)
from core.models import Program


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
        "email": "teacher@su.edu.kg",
        "first_name": "Teacher",
        "last_name": "Demo",
        "role": RoleCode.TEACHER,
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


class Command(BaseCommand):
    help = "Create idempotent Release 1 demo roles and users."

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
        users = {
            config["role"]: self._ensure_user(
                config,
                roles[config["role"]],
                options["password"],
            )
            for config in DEMO_USERS
        }
        self._ensure_profiles(users)

        self.stdout.write(
            self.style.SUCCESS(
                "Release 1 demo data is ready: "
                "4 users, 6 roles, teacher and student profiles."
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

    def _ensure_user(self, config, role, password):
        matches = User.objects.filter(email__iexact=config["email"])
        if matches.count() > 1:
            raise CommandError(
                f"Multiple users use demo email {config['email']}."
            )

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
