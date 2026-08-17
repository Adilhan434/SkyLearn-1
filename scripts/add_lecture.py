from datetime import date

from bootstrap import setup_django

setup_django()

from accounts.models import User, Group
from core.models import Course, CourseAllocation, Semester
from attendance.models import ScheduleItem, LessonTime

def add_lecture():
    try:
        lecturer = User.objects.get(id=2)
        course = Course.objects.get(id=1)
        group = Group.objects.get(id=1)
        semester = Semester.objects.get(id=1)
        lesson_time = LessonTime.objects.get(id=1)

        # 1. Create Allocation if not exists
        allocation, created = CourseAllocation.objects.get_or_create(
            lecturer=lecturer,
            semester=semester,
            group=group
        )
        allocation.courses.add(course)
        print(f"Course Allocation {'created' if created else 'already exists'}")

        # 2. Create Schedule Item
        _, created = ScheduleItem.objects.get_or_create(
            course=course,
            group=group,
            lesson_time=lesson_time,
            day='Monday',
            defaults={'date': date.today()}
        )
        print(f"Schedule Item {'created' if created else 'already exists'}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    add_lecture()
