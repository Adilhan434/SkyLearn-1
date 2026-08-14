from django.db import IntegrityError, transaction

from api.v1.exceptions import CodedAPIException
from courses.models import Course, CourseStatus
from learning.models import (
    CourseModule,
    CourseTopic,
    LearningMaterial,
    Lesson,
    ReleaseType,
)


COURSE_FIELDS = (
    "description",
    "language",
    "credits",
    "semester",
    "faculty",
    "department",
    "program",
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


def _file_name(field_file):
    return field_file.name if field_file else ""


def course_copy_queryset():
    return Course.objects.prefetch_related(
        "modules__topics__lessons__materials",
    )


@transaction.atomic
def copy_course(source, title, code, actor):
    """Copy a consistent course-content snapshot into a new draft course."""

    source = course_copy_queryset().select_for_update().get(pk=source.pk)
    course_values = {field: getattr(source, field) for field in COURSE_FIELDS}
    try:
        with transaction.atomic():
            copied_course = Course.objects.create(
                title=title,
                code=code,
                status=CourseStatus.DRAFT,
                cover=_file_name(source.cover),
                syllabus=_file_name(source.syllabus),
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
    source_lessons = []
    for source_module in source.modules.all():
        copied_module = CourseModule.objects.create(
            course=copied_course,
            title=source_module.title,
            description=source_module.description,
            order=source_module.order,
            release_type=source_module.release_type,
            release_at=source_module.release_at,
            created_by=actor,
            updated_by=actor,
        )
        for source_topic in source_module.topics.all():
            copied_topic = CourseTopic.objects.create(
                module=copied_module,
                title=source_topic.title,
                description=source_topic.description,
                order=source_topic.order,
                created_by=actor,
                updated_by=actor,
            )
            for source_lesson in source_topic.lessons.all():
                copied_lesson = Lesson.objects.create(
                    topic=copied_topic,
                    title=source_lesson.title,
                    description=source_lesson.description,
                    lesson_type=source_lesson.lesson_type,
                    content=source_lesson.content,
                    estimated_duration_minutes=(
                        source_lesson.estimated_duration_minutes
                    ),
                    order=source_lesson.order,
                    release_type=ReleaseType.ALWAYS,
                    release_at=None,
                    required_lesson=None,
                    is_published=False,
                    created_by=actor,
                    updated_by=actor,
                )
                lesson_map[source_lesson.pk] = copied_lesson
                source_lessons.append(source_lesson)

    for source_lesson in source_lessons:
        copied_lesson = lesson_map[source_lesson.pk]
        copied_lesson.release_type = source_lesson.release_type
        copied_lesson.release_at = source_lesson.release_at
        copied_lesson.required_lesson = (
            lesson_map[source_lesson.required_lesson_id]
            if source_lesson.required_lesson_id
            else None
        )
        copied_lesson.save(
            update_fields=(
                "release_type",
                "release_at",
                "required_lesson",
                "updated_at",
            )
        )
        for source_material in source_lesson.materials.all():
            material_values = {
                field: getattr(source_material, field) for field in MATERIAL_FIELDS
            }
            LearningMaterial.objects.create(
                lesson=copied_lesson,
                course=copied_course,
                file=_file_name(source_material.file),
                created_by=actor,
                updated_by=actor,
                **material_values,
            )

    return copied_course
