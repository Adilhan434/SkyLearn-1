from django.db import IntegrityError, transaction
from django.utils.dateparse import parse_date, parse_datetime

from api.v1.exceptions import CodedAPIException
from audit.models import CourseHistoryAction, CourseHistoryObjectType
from audit.services import record_course_history_event
from courses.models import Course, CourseStatus
from learning.models import (
    CourseModule,
    CourseTopic,
    LearningMaterial,
    Lesson,
    ReleaseType,
)
from organization.models import Department, Faculty, Program, Semester


SNAPSHOT_VERSION = 1
COURSE_FIELDS = (
    "description",
    "language",
    "credits",
    "start_date",
    "end_date",
)
MATERIAL_FIELDS = (
    "title",
    "description",
    "type",
    "external_url",
    "original_filename",
    "mime_type",
    "size",
    "extension",
    "download_allowed",
    "video_status",
    "duration_seconds",
)


class CourseCodeExists(CodedAPIException):
    error_code = "course_code_exists"
    default_detail = "A course with this code already exists."


class InvalidCourseTemplate(CodedAPIException):
    error_code = "invalid_course_template"
    default_detail = "The course template snapshot is invalid."


def _file_name(field_file):
    return field_file.name if field_file else ""


def _isoformat(value):
    return value.isoformat() if value is not None else None


def course_copy_queryset():
    return Course.objects.prefetch_related(
        "modules__topics__lessons__materials",
    )


def build_course_snapshot(source):
    """Return JSON without source Course or learning-content IDs."""

    lesson_references = {}
    lesson_number = 0
    for module in source.modules.all():
        for topic in module.topics.all():
            for lesson in topic.lessons.all():
                lesson_number += 1
                lesson_references[lesson.pk] = f"lesson-{lesson_number}"

    modules = []
    for module in source.modules.all():
        module_data = {
            "title": module.title,
            "description": module.description,
            "order": module.order,
            "release_type": module.release_type,
            "release_at": _isoformat(module.release_at),
            "topics": [],
        }
        for topic in module.topics.all():
            topic_data = {
                "title": topic.title,
                "description": topic.description,
                "order": topic.order,
                "lessons": [],
            }
            for lesson in topic.lessons.all():
                materials = []
                for material in lesson.materials.all():
                    material_data = {
                        field: getattr(material, field) for field in MATERIAL_FIELDS
                    }
                    material_data["file"] = _file_name(material.file)
                    materials.append(material_data)
                topic_data["lessons"].append(
                    {
                        "ref": lesson_references[lesson.pk],
                        "title": lesson.title,
                        "description": lesson.description,
                        "lesson_type": lesson.lesson_type,
                        "content": lesson.content,
                        "estimated_duration_minutes": (
                            lesson.estimated_duration_minutes
                        ),
                        "order": lesson.order,
                        "release_type": lesson.release_type,
                        "release_at": _isoformat(lesson.release_at),
                        "required_lesson_ref": lesson_references.get(
                            lesson.required_lesson_id
                        ),
                        "materials": materials,
                    }
                )
            module_data["topics"].append(topic_data)
        modules.append(module_data)

    course_data = {field: getattr(source, field) for field in COURSE_FIELDS}
    course_data["start_date"] = _isoformat(source.start_date)
    course_data["end_date"] = _isoformat(source.end_date)
    course_data.update(
        {
            "semester_id": source.semester_id,
            "faculty_id": source.faculty_id,
            "department_id": source.department_id,
            "program_id": source.program_id,
            "cover": _file_name(source.cover),
            "syllabus": _file_name(source.syllabus),
        }
    )
    return {
        "version": SNAPSHOT_VERSION,
        "course": course_data,
        "modules": modules,
    }


def _active_organization(model, object_id):
    return model.objects.get(pk=object_id, is_active=True)


def _course_values_from_snapshot(snapshot):
    if snapshot.get("version") != SNAPSHOT_VERSION:
        raise InvalidCourseTemplate()
    values = snapshot["course"]
    faculty = _active_organization(Faculty, values["faculty_id"])
    department = _active_organization(Department, values["department_id"])
    program = _active_organization(Program, values["program_id"])
    semester = _active_organization(Semester, values["semester_id"])
    if department.faculty_id != faculty.pk or program.department_id != department.pk:
        raise InvalidCourseTemplate()
    return {
        "description": values["description"],
        "language": values["language"],
        "credits": values["credits"],
        "semester": semester,
        "faculty": faculty,
        "department": department,
        "program": program,
        "start_date": parse_date(values["start_date"]),
        "end_date": parse_date(values["end_date"]),
        "cover": values["cover"],
        "syllabus": values["syllabus"],
    }


@transaction.atomic
def create_course_from_snapshot(snapshot, title, code, actor):
    """Create a new Draft from a validated snapshot as one transaction."""

    try:
        course_values = _course_values_from_snapshot(snapshot)
        modules = snapshot["modules"]
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise InvalidCourseTemplate() from exc
    except (
        Faculty.DoesNotExist,
        Department.DoesNotExist,
        Program.DoesNotExist,
        Semester.DoesNotExist,
    ) as exc:
        raise InvalidCourseTemplate() from exc

    if not course_values["start_date"] or not course_values["end_date"]:
        raise InvalidCourseTemplate()
    try:
        with transaction.atomic():
            copied_course = Course.objects.create(
                title=title,
                code=code,
                status=CourseStatus.DRAFT,
                review_comment="",
                published_at=None,
                published_by=None,
                created_by=actor,
                updated_by=actor,
                **course_values,
            )
    except IntegrityError as exc:
        raise CourseCodeExists() from exc

    lesson_map = {}
    pending_lessons = []
    try:
        for module_data in modules:
            copied_module = CourseModule.objects.create(
                course=copied_course,
                title=module_data["title"],
                description=module_data["description"],
                order=module_data["order"],
                release_type=module_data["release_type"],
                release_at=parse_datetime(module_data["release_at"])
                if module_data["release_at"]
                else None,
                created_by=actor,
                updated_by=actor,
            )
            for topic_data in module_data["topics"]:
                copied_topic = CourseTopic.objects.create(
                    module=copied_module,
                    title=topic_data["title"],
                    description=topic_data["description"],
                    order=topic_data["order"],
                    created_by=actor,
                    updated_by=actor,
                )
                for lesson_data in topic_data["lessons"]:
                    copied_lesson = Lesson.objects.create(
                        topic=copied_topic,
                        title=lesson_data["title"],
                        description=lesson_data["description"],
                        lesson_type=lesson_data["lesson_type"],
                        content=lesson_data["content"],
                        estimated_duration_minutes=lesson_data[
                            "estimated_duration_minutes"
                        ],
                        order=lesson_data["order"],
                        release_type=ReleaseType.ALWAYS,
                        release_at=None,
                        required_lesson=None,
                        is_published=False,
                        created_by=actor,
                        updated_by=actor,
                    )
                    reference = lesson_data["ref"]
                    if reference in lesson_map:
                        raise InvalidCourseTemplate()
                    lesson_map[reference] = copied_lesson
                    pending_lessons.append((copied_lesson, lesson_data))

        for copied_lesson, lesson_data in pending_lessons:
            required_reference = lesson_data["required_lesson_ref"]
            copied_lesson.release_type = lesson_data["release_type"]
            copied_lesson.release_at = (
                parse_datetime(lesson_data["release_at"])
                if lesson_data["release_at"]
                else None
            )
            copied_lesson.required_lesson = (
                lesson_map[required_reference] if required_reference else None
            )
            copied_lesson.save(
                update_fields=(
                    "release_type",
                    "release_at",
                    "required_lesson",
                    "updated_at",
                )
            )
            for material_data in lesson_data["materials"]:
                material_values = {
                    field: material_data[field] for field in MATERIAL_FIELDS
                }
                LearningMaterial.objects.create(
                    lesson=copied_lesson,
                    course=copied_course,
                    file=material_data["file"],
                    created_by=actor,
                    updated_by=actor,
                    **material_values,
                )
    except (KeyError, TypeError, ValueError, IntegrityError) as exc:
        raise InvalidCourseTemplate() from exc

    return copied_course


@transaction.atomic
def copy_course(source, title, code, actor):
    """Copy a consistent course-content snapshot into a new draft course."""

    source = course_copy_queryset().select_for_update().get(pk=source.pk)
    snapshot = build_course_snapshot(source)
    copied_course = create_course_from_snapshot(snapshot, title, code, actor)
    record_course_history_event(
        course=copied_course,
        action=CourseHistoryAction.COPIED,
        actor=actor,
        object_type=CourseHistoryObjectType.COURSE,
        object_id=copied_course.pk,
        object_title=copied_course.title,
        details={
            "source_course_id": source.pk,
            "source_course_code": source.code,
        },
    )
    record_course_history_event(
        course=source,
        action=CourseHistoryAction.COPIED,
        actor=actor,
        object_type=CourseHistoryObjectType.COURSE,
        object_id=copied_course.pk,
        object_title=copied_course.title,
        details={
            "target_course_id": copied_course.pk,
            "target_course_code": copied_course.code,
        },
    )
    return copied_course
