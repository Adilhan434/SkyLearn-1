from datetime import date, datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

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
from calendar_events.models import CalendarEvent, CalendarEventType
from courses.models import (
    Course,
    CourseLanguage,
    CourseStatus,
    CourseTeachingAssignment,
    CourseTeachingRole,
)
from core.models import Program
from enrollments.models import Enrollment, EnrollmentSource, EnrollmentStatus
from learning.models import (
    CourseModule,
    CourseTopic,
    LearningMaterial,
    LearningMaterialType,
    Lesson,
    LessonType,
)
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

COURSES = (
    (
        "CS101",
        "Introduction to Programming",
        CourseStatus.PUBLISHED,
        "SE",
        "Fall 2026",
        CourseLanguage.ENGLISH,
        5,
    ),
    (
        "CS201",
        "Data Structures",
        CourseStatus.PUBLISHED,
        "CS-BSC",
        "Fall 2026",
        CourseLanguage.ENGLISH,
        5,
    ),
    (
        "EE101",
        "Electrical Circuits",
        CourseStatus.PUBLISHED,
        "EE-BSC",
        "Fall 2026",
        CourseLanguage.ENGLISH,
        4,
    ),
    (
        "BUS101",
        "Business Fundamentals",
        CourseStatus.PUBLISHED,
        "BBA",
        "Fall 2026",
        CourseLanguage.RUSSIAN,
        4,
    ),
    (
        "CS001",
        "Digital Literacy",
        CourseStatus.DRAFT,
        "CS-BSC",
        "Spring 2027",
        CourseLanguage.ENGLISH,
        3,
    ),
    (
        "BUS001",
        "Academic Communication",
        CourseStatus.DRAFT,
        "BBA",
        "Spring 2027",
        CourseLanguage.RUSSIAN,
        3,
    ),
    (
        "EE201",
        "Digital Electronics",
        CourseStatus.UNDER_REVIEW,
        "EE-BSC",
        "Spring 2027",
        CourseLanguage.ENGLISH,
        5,
    ),
    (
        "BUS201",
        "Principles of Management",
        CourseStatus.UNDER_REVIEW,
        "BBA",
        "Spring 2027",
        CourseLanguage.RUSSIAN,
        5,
    ),
    (
        "CS301",
        "Software Architecture",
        CourseStatus.ARCHIVED,
        "SE",
        "Fall 2026",
        CourseLanguage.ENGLISH,
        5,
    ),
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
        actor = users[RoleCode.LMS_ADMIN]
        organization = self._ensure_organization(actor)
        courses = self._ensure_courses(users, organization, actor)
        lessons = self._ensure_course_structure(courses, actor)
        self._ensure_materials(lessons, actor)
        self._ensure_enrollments(courses, users[RoleCode.STUDENT], actor)
        self._ensure_calendar(courses, actor)

        self.stdout.write(
            self.style.SUCCESS(
                "Release 1 demo data is ready: "
                "6 users, 6 roles, teacher and student profiles, "
                "3 faculties, 5 departments, 5 programs, 4 groups, "
                "2 semesters, 9 courses, 20 modules, 30 topics, "
                "50 lessons, 30 materials, 4 enrollments, and 15 events."
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

        semesters = {}
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
            semesters[name] = semester

        return {
            "faculties": faculties,
            "departments": departments,
            "programs": programs,
            "semesters": semesters,
        }

    def _ensure_courses(self, users, organization, actor):
        courses = []
        published_at = timezone.make_aware(datetime(2026, 8, 1, 9, 0))
        teacher = users[RoleCode.TEACHER]
        assistant = users[RoleCode.TEACHING_ASSISTANT]

        for (
            code,
            title,
            status,
            program_code,
            semester_name,
            language,
            credits,
        ) in COURSES:
            program = organization["programs"][program_code]
            semester = organization["semesters"][semester_name]
            course = Course.objects.filter(code__iexact=code).first()
            if course is None:
                course = Course(code=code, created_by=actor)
            course.title = title
            course.description = f"Release 1 demo course: {title}."
            course.language = language
            course.credits = credits
            course.semester = semester
            course.faculty = program.department.faculty
            course.department = program.department
            course.program = program
            course.status = status
            course.start_date = semester.start_date
            course.end_date = semester.end_date
            course.published_at = (
                published_at
                if status in {CourseStatus.PUBLISHED, CourseStatus.ARCHIVED}
                else None
            )
            course.published_by = (
                actor
                if status in {CourseStatus.PUBLISHED, CourseStatus.ARCHIVED}
                else None
            )
            course.updated_by = actor
            course.full_clean()
            course.save(allow_archived_update=True)
            courses.append(course)

            CourseTeachingAssignment.objects.update_or_create(
                course=course,
                user=teacher,
                defaults={
                    "role": CourseTeachingRole.TEACHER,
                    "is_primary": True,
                    "created_by": actor,
                    "updated_by": actor,
                },
            )
            CourseTeachingAssignment.objects.update_or_create(
                course=course,
                user=assistant,
                defaults={
                    "role": CourseTeachingRole.TEACHING_ASSISTANT,
                    "is_primary": False,
                    "created_by": actor,
                    "updated_by": actor,
                },
            )

        return courses

    def _ensure_course_structure(self, courses, actor):
        lessons = []
        module_number = 0
        topic_number = 0

        for course_index, course in enumerate(courses):
            module_count = 3 if course_index < 2 else 2
            for module_order in range(1, module_count + 1):
                module_number += 1
                module, _ = CourseModule.objects.update_or_create(
                    course=course,
                    order=module_order,
                    defaults={
                        "title": f"Module {module_order}",
                        "description": "Release 1 demo module.",
                        "created_by": actor,
                        "updated_by": actor,
                    },
                )
                topic_count = 2 if module_number <= 10 else 1
                for topic_order in range(1, topic_count + 1):
                    topic_number += 1
                    topic, _ = CourseTopic.objects.update_or_create(
                        module=module,
                        order=topic_order,
                        defaults={
                            "title": f"Topic {module_order}.{topic_order}",
                            "description": "Release 1 demo topic.",
                            "created_by": actor,
                            "updated_by": actor,
                        },
                    )
                    lesson_count = 2 if topic_number <= 20 else 1
                    for lesson_order in range(1, lesson_count + 1):
                        lesson, _ = Lesson.objects.update_or_create(
                            topic=topic,
                            order=lesson_order,
                            defaults={
                                "title": (
                                    f"Lesson {module_order}."
                                    f"{topic_order}.{lesson_order}"
                                ),
                                "description": "Release 1 demo lesson.",
                                "lesson_type": LessonType.TEXT,
                                "content": "Demo learning content.",
                                "estimated_duration_minutes": 30,
                                "is_published": (
                                    course.status == CourseStatus.PUBLISHED
                                ),
                                "created_by": actor,
                                "updated_by": actor,
                            },
                        )
                        lessons.append(lesson)

        return lessons

    def _ensure_materials(self, lessons, actor):
        for lesson in lessons[:30]:
            LearningMaterial.objects.update_or_create(
                lesson=lesson,
                title="Release 1 reference",
                defaults={
                    "course": lesson.course,
                    "description": "External demo learning resource.",
                    "type": LearningMaterialType.EXTERNAL_LINK,
                    "external_url": (
                        "https://example.com/release1/"
                        f"{lesson.course.code.lower()}/lesson-{lesson.pk}"
                    ),
                    "download_allowed": False,
                    "created_by": actor,
                    "updated_by": actor,
                },
            )

    def _ensure_enrollments(self, courses, student, actor):
        published_courses = [
            course for course in courses if course.status == CourseStatus.PUBLISHED
        ]
        for course in published_courses:
            Enrollment.objects.update_or_create(
                student=student,
                course=course,
                defaults={
                    "status": EnrollmentStatus.ACTIVE,
                    "source": EnrollmentSource.MANUAL,
                    "created_by": actor,
                    "updated_by": actor,
                },
            )

    def _ensure_calendar(self, courses, actor):
        published_courses = [
            course for course in courses if course.status == CourseStatus.PUBLISHED
        ]
        event_types = (
            CalendarEventType.COURSE_START,
            CalendarEventType.MODULE_RELEASE,
            CalendarEventType.LESSON_RELEASE,
            CalendarEventType.CUSTOM,
        )
        starts_at = timezone.make_aware(datetime(2026, 9, 1, 9, 0))

        for event_index in range(15):
            course = published_courses[event_index % len(published_courses)]
            start_at = starts_at + timedelta(days=event_index)
            CalendarEvent.objects.update_or_create(
                course=course,
                title=f"Release 1 event {event_index + 1}",
                defaults={
                    "description": "Release 1 demo calendar event.",
                    "event_type": event_types[event_index % len(event_types)],
                    "start_at": start_at,
                    "end_at": start_at + timedelta(hours=1),
                    "is_public": True,
                    "created_by": actor,
                    "updated_by": actor,
                },
            )
