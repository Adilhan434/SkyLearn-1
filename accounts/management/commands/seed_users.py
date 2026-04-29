"""
Seed test users for every role: admin / lecturer / student / accountant / parent.

Usage:
    python manage.py seed_users
    python manage.py seed_users --reset    # wipe seeded users first

All seeded users share the password "Test1234!" for easy local testing.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Group, Lecturer, Parent, Student
from attendance.models import Attendance, LessonTime, ScheduleItem
from core.models import (
    AcademicYear,
    Course,
    CourseAllocation,
    Module,
    Notification,
    Program,
    Semester,
)
from finance.models import Contract, Invoice, Payment
from result.models import Grade_1st_module, Grade_2nd_module, Grade_semester


PASSWORD = "Test1234!"

SEED_USERNAMES = [
    "admin_demo",
    "teacher_demo",
    "student_demo",
    "accountant_demo",
    "parent_demo",
]


class Command(BaseCommand):
    help = "Seed test users (admin/teacher/student/accountant/parent) with related demo data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete previously seeded users before creating new ones.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        User = get_user_model()

        if opts["reset"]:
            self.stdout.write(self.style.WARNING("Resetting previously seeded users..."))
            User.objects.filter(username__in=SEED_USERNAMES).delete()

        # ---------- ADMIN ----------
        admin, created = User.objects.get_or_create(
            username="admin_demo",
            defaults=dict(
                email="admin@demo.local",
                first_name="Admin",
                last_name="Demo",
                is_staff=True,
                is_superuser=True,
            ),
        )
        admin.set_password(PASSWORD)
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        self._log("admin_demo", created)

        # ---------- ACCOUNTANT ----------
        accountant, created = User.objects.get_or_create(
            username="accountant_demo",
            defaults=dict(
                email="accountant@demo.local",
                first_name="Anara",
                last_name="Bookkeeper",
                phone="+996700111222",
                gender="F",
            ),
        )
        accountant.is_accountant = True
        accountant.set_password(PASSWORD)
        accountant.save()
        self._log("accountant_demo", created)

        # ---------- LECTURER ----------
        teacher, created = User.objects.get_or_create(
            username="teacher_demo",
            defaults=dict(
                email="teacher@demo.local",
                first_name="Tanya",
                last_name="Lecturer",
                phone="+996700222333",
                gender="F",
                address="Bishkek, Chui Ave 100",
            ),
        )
        teacher.is_lecturer = True
        teacher.set_password(PASSWORD)
        teacher.save()
        Lecturer.objects.get_or_create(lecturer=teacher, defaults={"admin": admin})
        self._log("teacher_demo", created)

        # ---------- Program / AcademicYear / Semester / Course ----------
        program, _ = Program.objects.get_or_create(
            name="Computer Science", defaults={"admin": admin}
        )
        ay, _ = AcademicYear.objects.get_or_create(
            year=date.today().year,
            program=program,
            defaults={"admin": admin, "is_current": True},
        )
        semester, _ = Semester.objects.get_or_create(
            name="First",
            academic_year=ay,
            defaults={"admin": admin, "is_current": True},
        )
        Module.objects.get_or_create(
            name="First", semester=semester, defaults={"admin": admin, "is_current": True}
        )
        course1, _ = Course.objects.get_or_create(
            name="Introduction to Python",
            defaults={"admin": admin, "description": "Beginner Python course."},
        )
        course2, _ = Course.objects.get_or_create(
            name="Web Development",
            defaults={"admin": admin, "description": "HTML, CSS, JS, React."},
        )
        semester.courses.add(course1, course2)

        group, _ = Group.objects.get_or_create(
            name="CS-101", program=program, defaults={"admin": admin}
        )

        # ---------- STUDENT ----------
        student_user, created = User.objects.get_or_create(
            username="student_demo",
            defaults=dict(
                email="student@demo.local",
                first_name="Sasha",
                last_name="Student",
                phone="+996700333444",
                gender="M",
                address="Bishkek, Manas 50",
            ),
        )
        student_user.is_student = True
        student_user.set_password(PASSWORD)
        student_user.save()
        student, _ = Student.objects.get_or_create(
            student=student_user,
            defaults={"group": group, "admin": admin},
        )
        if not student.group:
            student.group = group
            student.admin = admin
            student.save()
        self._log("student_demo", created)

        # ---------- PARENT ----------
        parent_user, created = User.objects.get_or_create(
            username="parent_demo",
            defaults=dict(
                email="parent@demo.local",
                first_name="Pavel",
                last_name="Parent",
                phone="+996700444555",
                gender="M",
            ),
        )
        parent_user.is_parent = True
        parent_user.set_password(PASSWORD)
        parent_user.save()
        Parent.objects.get_or_create(
            user=parent_user,
            defaults={
                "student": student,
                "first_name": "Pavel",
                "last_name": "Parent",
                "phone": "+996700444555",
                "email": "parent@demo.local",
                "relation_ship": "Father",
                "admin": admin,
            },
        )
        self._log("parent_demo", created)

        # ---------- Course allocation ----------
        allocation, _ = CourseAllocation.objects.get_or_create(
            lecturer=teacher,
            semester=semester,
            group=group,
            defaults={"admin": admin},
        )
        allocation.courses.add(course1, course2)

        # ---------- Lesson times + schedule + attendance ----------
        from datetime import time as dtime

        lt1, _ = LessonTime.objects.get_or_create(
            order=1,
            admin=admin,
            defaults={"start_time": dtime(9, 0), "end_time": dtime(10, 30)},
        )
        lt2, _ = LessonTime.objects.get_or_create(
            order=2,
            admin=admin,
            defaults={"start_time": dtime(10, 45), "end_time": dtime(12, 15)},
        )
        today = date.today()
        sched1, _ = ScheduleItem.objects.get_or_create(
            course=course1,
            group=group,
            lesson_time=lt1,
            day="Monday",
            date=today,
            defaults={"admin": admin},
        )
        sched2, _ = ScheduleItem.objects.get_or_create(
            course=course2,
            group=group,
            lesson_time=lt2,
            day="Wednesday",
            date=today + timedelta(days=2),
            defaults={"admin": admin},
        )

        Attendance.objects.get_or_create(
            Student=student, shcedule=sched1, defaults={"status": True, "admin": admin}
        )
        Attendance.objects.get_or_create(
            Student=student, shcedule=sched2, defaults={"status": True, "admin": admin}
        )

        # ---------- Grades ----------
        Grade_1st_module.objects.update_or_create(
            student=student,
            course=course1,
            defaults=dict(
                lecturer=teacher,
                attendance=Decimal("9.00"),
                activities=Decimal("18.00"),
                exam=Decimal("45.00"),
                total=Decimal("72.00"),
                grade="B",
                admin=admin,
            ),
        )
        Grade_semester.objects.update_or_create(
            student=student,
            course=course1,
            semester=semester,
            defaults=dict(
                lecturer=teacher,
                attendance=Decimal("9.00"),
                activities=Decimal("18.00"),
                exam=Decimal("60.00"),
                total=Decimal("87.00"),
                grade="A",
                admin=admin,
            ),
        )
        Grade_semester.objects.update_or_create(
            student=student,
            course=course2,
            semester=semester,
            defaults=dict(
                lecturer=teacher,
                attendance=Decimal("8.00"),
                activities=Decimal("16.00"),
                exam=Decimal("52.00"),
                total=Decimal("76.00"),
                grade="B+",
                admin=admin,
            ),
        )

        # ---------- Finance ----------
        invoice, _ = Invoice.objects.get_or_create(
            student=student,
            title="Tuition Fee — Semester 1",
            defaults={
                "amount": Decimal("50000.00"),
                "due_date": today + timedelta(days=30),
                "status": "pending",
                "admin": admin,
            },
        )
        Payment.objects.get_or_create(
            invoice=invoice,
            student=student,
            amount=Decimal("20000.00"),
            defaults={
                "payment_method": "cash",
                "status": "approved",
                "admin": admin,
            },
        )
        invoice.update_status()

        Contract.objects.get_or_create(
            contract_number="DEMO-0001",
            defaults={
                "student": student,
                "title": "Educational Services Contract",
                "amount": Decimal("100000.00"),
                "start_date": today,
                "end_date": today + timedelta(days=365),
                "is_active": True,
                "admin": admin,
            },
        )

        # ---------- Notifications ----------
        Notification.objects.get_or_create(
            recipient=student_user,
            title="Welcome!",
            defaults={
                "sender": admin,
                "message": "Welcome to the LMS. Your dashboard is ready.",
                "notification_type": "info",
            },
        )
        Notification.objects.get_or_create(
            recipient=parent_user,
            title="Welcome, parent!",
            defaults={
                "sender": admin,
                "message": "You can now monitor your child's progress.",
                "notification_type": "info",
            },
        )

        self.stdout.write(self.style.SUCCESS("\nSeeding finished."))
        self.stdout.write("  Users (password = Test1234!):")
        for u in SEED_USERNAMES:
            self.stdout.write(f"    - {u}")

    def _log(self, username, created):
        verb = "CREATED" if created else "UPDATED"
        self.stdout.write(f"  [{verb}] {username}")
