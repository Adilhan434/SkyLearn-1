from django.test import TestCase
from accounts.filters import LecturerFilter, StudentFilter
from accounts.models import Group, User, Student
from core.models import Program


class LecturerFilterTestCase(TestCase):
    def setUp(self):
        User.objects.create(
            username="user1",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
        )
        User.objects.create(
            username="user2",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
        )
        User.objects.create(
            username="user3",
            first_name="Alice",
            last_name="Smith",
            email="alice@example.com",
        )

    def test_username_filter(self):
        filter_set = LecturerFilter(data={"username": "user1"})
        self.assertEqual(len(filter_set.qs), 1)

    def test_name_filter(self):
        filter_set = LecturerFilter(data={"name": "John"})
        self.assertEqual(len(filter_set.qs), 1)

    def test_email_filter(self):
        filter_set = LecturerFilter(data={"email": "example.com"})
        self.assertEqual(
            len(filter_set.qs), 3
        )  # All users should be returned since all have email addresses with "example.com"

    def test_combined_filters(self):
        filter_set = LecturerFilter(data={"name": "Doe", "email": "example.com"})
        self.assertEqual(
            len(filter_set.qs), 2
        )  # Both John Doe and Jane Doe should be returned

        filter_set = LecturerFilter(data={"name": "Alice", "email": "example.com"})
        self.assertEqual(
            len(filter_set.qs), 1
        )  # 1 user matches Alice with "example.com" in the email

    def test_no_filters(self):
        filter_set = LecturerFilter(data={})
        self.assertEqual(
            len(filter_set.qs), 3
        )  # All users should be returned since no filters are applied


class StudentFilterTestCase(TestCase):
    def setUp(self):
        program1 = Program.objects.create(name="Computer Science")
        program2 = Program.objects.create(name="Mathematics")
        program3 = Program.objects.create(name="Computer Engineering")
        group1 = Group.objects.create(name="CS-1", program=program1)
        group2 = Group.objects.create(name="MATH-1", program=program2)
        group3 = Group.objects.create(name="CE-1", program=program3)

        Student.objects.create(
            student=User.objects.create(
                username="student1",
                first_name="John",
                last_name="Doe",
                email="john@example.com",
            ),
            group=group1,
        )
        Student.objects.create(
            student=User.objects.create(
                username="student2",
                first_name="Jane",
                last_name="Williams",
                email="jane@example.com",
            ),
            group=group2,
        )
        Student.objects.create(
            student=User.objects.create(
                username="student3",
                first_name="Alice",
                last_name="Smith",
                email="alice@example.com",
            ),
            group=group3,
        )

    def test_name_filter(self):
        filtered_students = StudentFilter(
            data={"name": "John"}, queryset=Student.objects.all()
        ).qs
        self.assertEqual(filtered_students.count(), 1)

    def test_email_filter(self):
        filter_set = StudentFilter(data={"email": "example.com"})
        self.assertEqual(
            len(filter_set.qs), 3
        )  # All students should be returned since all have email addresses with "example.com"

    def test_program_filter(self):
        filter_set = StudentFilter(
            data={"program": "Computer Science"}, queryset=Student.objects.all()
        )
        self.assertEqual(len(filter_set.qs), 1)
