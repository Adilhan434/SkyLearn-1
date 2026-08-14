from dataclasses import dataclass

from courses.models import CourseTeachingRole


@dataclass(frozen=True)
class ReadinessCheck:
    key: str
    status: str
    weight: int
    message: str = ""
    blocking: bool = True

    def as_dict(self):
        result = {"key": self.key, "status": self.status}
        if self.message:
            result["message"] = self.message
        return result


def _metadata_check(course):
    errors = []
    for field_name, value in (
        ("title", course.title),
        ("code", course.code),
        ("faculty", course.faculty_id),
        ("department", course.department_id),
        ("program", course.program_id),
        ("semester", course.semester_id),
    ):
        if not value:
            errors.append(f"Course {field_name} is missing.")

    for label, organization_object in (
        ("Faculty", course.faculty),
        ("Department", course.department),
        ("Program", course.program),
        ("Semester", course.semester),
    ):
        if not organization_object.is_active:
            errors.append(f"{label} is inactive.")

    if course.department.faculty_id != course.faculty_id:
        errors.append("Department does not belong to the selected faculty.")
    if course.program.department_id != course.department_id:
        errors.append("Program does not belong to the selected department.")
    if course.end_date < course.start_date:
        errors.append("Course end date is before its start date.")

    if errors:
        return ReadinessCheck(
            key="metadata",
            status="error",
            weight=50,
            message=" ".join(errors),
        )
    return ReadinessCheck(key="metadata", status="complete", weight=50)


def _teacher_check(course):
    has_primary_teacher = course.teaching_assignments.filter(
        role=CourseTeachingRole.TEACHER,
        is_primary=True,
        user__is_active=True,
    ).exists()
    if not has_primary_teacher:
        return ReadinessCheck(
            key="teacher",
            status="error",
            weight=30,
            message="Course has no active primary teacher.",
        )
    return ReadinessCheck(key="teacher", status="complete", weight=30)


def _syllabus_check(course):
    if not course.syllabus:
        return ReadinessCheck(
            key="syllabus",
            status="warning",
            weight=20,
            message="Course has no syllabus.",
            blocking=False,
        )
    return ReadinessCheck(
        key="syllabus",
        status="complete",
        weight=20,
        blocking=False,
    )


def evaluate_course_readiness(course):
    checks = (
        _metadata_check(course),
        _teacher_check(course),
        _syllabus_check(course),
    )
    score = sum(check.weight for check in checks if check.status == "complete")
    ready_for_review = not any(
        check.blocking and check.status != "complete" for check in checks
    )
    return {
        "score": score,
        "ready_for_review": ready_for_review,
        "checks": [check.as_dict() for check in checks],
    }


def review_readiness_errors(course):
    result = evaluate_course_readiness(course)
    return [
        check["message"]
        for check in result["checks"]
        if check["status"] == "error"
    ]
