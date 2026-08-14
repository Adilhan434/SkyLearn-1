from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import F
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
from calendar_events.models import CalendarEvent
from courses.models import (
    Course,
    CourseStatus,
    CourseTeachingAssignment,
    CourseTeachingRole,
)
from enrollments.models import Enrollment, EnrollmentStatus
from learning.models import CourseModule, CourseTopic, LearningMaterial, Lesson
from organization.models import Department, Faculty
from organization.models import Group as OrganizationGroup
from organization.models import Program as OrganizationProgram
from organization.models import Semester


class SeedRelease1CommandTests(TestCase):
    seeded_models = {
        "users": User,
        "roles": Role,
        "permissions": LMSPermission,
        "students": Student,
        "lecturers": Lecturer,
        "faculties": Faculty,
        "departments": Department,
        "organization_programs": OrganizationProgram,
        "organization_groups": OrganizationGroup,
        "semesters": Semester,
        "courses": Course,
        "assignments": CourseTeachingAssignment,
        "modules": CourseModule,
        "topics": CourseTopic,
        "lessons": Lesson,
        "materials": LearningMaterial,
        "enrollments": Enrollment,
        "events": CalendarEvent,
    }

    def run_seed(self, **options):
        output = StringIO()
        options.setdefault("allow_production", True)
        call_command("seed_release1", stdout=output, **options)
        return output.getvalue()

    def seeded_id_snapshot(self):
        return {
            name: list(model.objects.order_by("pk").values_list("pk", flat=True))
            for name, model in self.seeded_models.items()
        }

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

    def test_command_creates_release1_courses_and_learning_content(self):
        self.run_seed()

        seeded_courses = Course.objects.filter(
            code__in={
                "CS101",
                "CS201",
                "EE101",
                "BUS101",
                "CS001",
                "BUS001",
                "EE201",
                "BUS201",
                "CS301",
            }
        )
        self.assertEqual(seeded_courses.count(), 9)
        self.assertEqual(
            seeded_courses.filter(status=CourseStatus.DRAFT).count(),
            2,
        )
        self.assertEqual(
            seeded_courses.filter(status=CourseStatus.UNDER_REVIEW).count(),
            2,
        )
        self.assertEqual(
            seeded_courses.filter(status=CourseStatus.PUBLISHED).count(),
            4,
        )
        self.assertEqual(
            seeded_courses.filter(status=CourseStatus.ARCHIVED).count(),
            1,
        )
        self.assertEqual(
            CourseModule.objects.filter(course__in=seeded_courses).count(), 20
        )
        self.assertEqual(
            CourseTopic.objects.filter(module__course__in=seeded_courses).count(),
            30,
        )
        self.assertEqual(
            Lesson.objects.filter(topic__module__course__in=seeded_courses).count(),
            50,
        )
        self.assertEqual(
            LearningMaterial.objects.filter(course__in=seeded_courses).count(),
            30,
        )
        self.assertFalse(
            LearningMaterial.objects.exclude(
                course_id=F("lesson__topic__module__course_id")
            ).exists()
        )

        self.assertEqual(
            CourseTeachingAssignment.objects.filter(
                course__in=seeded_courses,
                role=CourseTeachingRole.TEACHER,
                is_primary=True,
            ).count(),
            9,
        )
        self.assertEqual(
            CourseTeachingAssignment.objects.filter(
                course__in=seeded_courses,
                role=CourseTeachingRole.TEACHING_ASSISTANT,
            ).count(),
            9,
        )

    def test_command_creates_student_enrollments_and_calendar_events(self):
        self.run_seed()

        student = User.objects.get(email="student@su.edu.kg")
        enrollments = Enrollment.objects.filter(student=student)
        self.assertEqual(enrollments.count(), 4)
        self.assertFalse(
            enrollments.exclude(
                status=EnrollmentStatus.ACTIVE,
                course__status=CourseStatus.PUBLISHED,
            ).exists()
        )

        events = CalendarEvent.objects.filter(title__startswith="Release 1 event ")
        self.assertEqual(events.count(), 15)
        self.assertFalse(
            events.exclude(
                is_public=True,
                course__status=CourseStatus.PUBLISHED,
            ).exists()
        )

    def test_command_is_idempotent(self):
        self.run_seed()
        original_ids = self.seeded_id_snapshot()

        self.run_seed()

        self.assertEqual(self.seeded_id_snapshot(), original_ids)

    def test_command_restores_seed_owned_fields_without_replacing_objects(self):
        self.run_seed()
        original_ids = self.seeded_id_snapshot()

        User.objects.filter(email="content@su.edu.kg").update(
            last_name="Changed",
            is_active=False,
        )
        Faculty.objects.filter(code="ENG").update(
            name="Changed faculty",
            is_active=False,
        )
        Course.objects.filter(code="CS101").update(
            title="Changed course",
            status=CourseStatus.DRAFT,
        )
        module = CourseModule.objects.get(course__code="CS101", order=1)
        CourseModule.objects.filter(pk=module.pk).update(title="Changed module")
        topic = CourseTopic.objects.get(module=module, order=1)
        CourseTopic.objects.filter(pk=topic.pk).update(title="Changed topic")
        lesson = Lesson.objects.get(topic=topic, order=1)
        Lesson.objects.filter(pk=lesson.pk).update(
            content="Changed content",
            is_published=False,
        )
        LearningMaterial.objects.filter(lesson=lesson).update(
            external_url="https://example.com/changed"
        )
        Enrollment.objects.filter(
            student__email="student@su.edu.kg",
            course__code="CS101",
        ).update(status=EnrollmentStatus.WITHDRAWN)
        CalendarEvent.objects.filter(
            title="Release 1 event 1",
        ).update(is_public=False)
        CourseTeachingAssignment.objects.filter(
            course__code="CS101",
            role=CourseTeachingRole.TEACHER,
        ).update(is_primary=False)

        self.run_seed()

        self.assertEqual(self.seeded_id_snapshot(), original_ids)
        content_manager = User.objects.get(email="content@su.edu.kg")
        self.assertEqual(content_manager.last_name, "Manager")
        self.assertTrue(content_manager.is_active)
        engineering = Faculty.objects.get(code="ENG")
        self.assertEqual(engineering.name, "Faculty of Engineering")
        self.assertTrue(engineering.is_active)
        course = Course.objects.get(code="CS101")
        self.assertEqual(course.title, "Introduction to Programming")
        self.assertEqual(course.status, CourseStatus.PUBLISHED)
        module.refresh_from_db()
        topic.refresh_from_db()
        lesson.refresh_from_db()
        self.assertEqual(module.title, "Module 1")
        self.assertEqual(topic.title, "Topic 1.1")
        self.assertEqual(lesson.content, "Demo learning content.")
        self.assertTrue(lesson.is_published)
        self.assertTrue(
            LearningMaterial.objects.get(lesson=lesson).external_url.startswith(
                "https://example.com/release1/"
            )
        )
        self.assertEqual(
            Enrollment.objects.get(
                student__email="student@su.edu.kg",
                course=course,
            ).status,
            EnrollmentStatus.ACTIVE,
        )
        self.assertTrue(CalendarEvent.objects.get(title="Release 1 event 1").is_public)
        self.assertTrue(
            CourseTeachingAssignment.objects.get(
                course=course,
                role=CourseTeachingRole.TEACHER,
            ).is_primary
        )

    def test_command_rolls_back_all_demo_data_when_seeding_fails(self):
        with patch(
            "accounts.management.commands.seed_release1.Command._ensure_calendar",
            side_effect=RuntimeError("seed failure"),
        ):
            with self.assertRaisesMessage(RuntimeError, "seed failure"):
                self.run_seed()

        self.assertFalse(User.objects.filter(email="student@su.edu.kg").exists())
        self.assertFalse(Faculty.objects.exists())
        self.assertFalse(Course.objects.exists())
        self.assertFalse(Lesson.objects.exists())

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
