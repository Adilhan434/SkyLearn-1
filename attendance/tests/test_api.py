from datetime import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Group, Student
from attendance.models import Attendance, LessonTime, ScheduleItem
from core.models import Course, Program


User = get_user_model()


class AttendanceFixturesMixin:
    def create_domain(self):
        self.program = Program.objects.create(name="Computer Science")
        self.course = Course.objects.create(name="Python Programming")
        self.group = Group.objects.create(name="Group A", program=self.program)
        self.lesson_time = LessonTime.objects.create(
            order=1,
            start_time=time(9, 0),
            end_time=time(10, 30),
        )
        self.schedule = ScheduleItem.objects.create(
            course=self.course,
            group=self.group,
            lesson_time=self.lesson_time,
            day="Monday",
        )

    def create_student(self, username="student"):
        user = User.objects.create_user(username=username, password="password123")
        student = Student.objects.create(student=user, group=self.group)
        return user, student


class AttendanceModelTests(AttendanceFixturesMixin, TestCase):
    def setUp(self):
        self.create_domain()
        _, self.student = self.create_student()

    def test_schedule_item_creation(self):
        self.assertEqual(self.schedule.course, self.course)
        self.assertEqual(self.schedule.start_time, time(9, 0))
        self.assertIn(self.course.name, str(self.schedule))

    def test_attendance_creation(self):
        attendance = Attendance.objects.create(
            Student=self.student,
            shcedule=self.schedule,
            status=True,
        )
        self.assertTrue(attendance.status)


class AttendanceAPITests(AttendanceFixturesMixin, APITestCase):
    def setUp(self):
        self.create_domain()
        self.student_user, self.student = self.create_student()
        self.attendance = Attendance.objects.create(
            Student=self.student,
            shcedule=self.schedule,
            status=True,
        )
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="admin123",
        )

    def test_unauthenticated_user_cannot_access_schedule(self):
        response = self.client.get("/attendance/schedules/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_can_view_own_schedule(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.get("/attendance/schedules/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_student_cannot_create_schedule(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.post(
            "/attendance/schedules/",
            {
                "course": self.course.pk,
                "group": self.group.pk,
                "lesson_time": self.lesson_time.pk,
                "day": "Tuesday",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_schedule(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/attendance/schedules/",
            {
                "course": self.course.pk,
                "group": self.group.pk,
                "lesson_time": self.lesson_time.pk,
                "day": "Tuesday",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_student_can_view_own_attendance(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.get("/attendance/attendances/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_student_cannot_update_attendance(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.patch(
            f"/attendance/attendances/{self.attendance.pk}/",
            {"status": False},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_attendance_statistics(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.get("/attendance/attendances/statistics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["present"], 1)
