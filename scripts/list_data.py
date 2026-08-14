from bootstrap import setup_django

setup_django()

from accounts.models import Group, Lecturer
from core.models import Course, AcademicYear
from attendance.models import LessonTime

print("--- Lecturers ---")
for l in Lecturer.objects.all():
    print(f"ID: {l.id}, Name: {l.lecturer.get_full_name()}, UserID: {l.lecturer.id}")

print("\n--- Courses ---")
for c in Course.objects.all():
    print(f"ID: {c.id}, Title: {c.name}")

print("\n--- Groups ---")
for g in Group.objects.all():
    print(f"ID: {g.id}, Name: {g.name}")

print("\n--- Session Times ---")
for s in LessonTime.objects.all():
    print(f"ID: {s.id}, Order: {s.order}, Time: {s.start_time}-{s.end_time}")

print("\n--- Academic Years ---")
for y in AcademicYear.objects.all():
    print(f"ID: {y.id}, Year: {y.year}")
