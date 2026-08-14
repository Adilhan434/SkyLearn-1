from django.db import migrations, models
from django.db.models.functions import Lower


def normalize_course_codes(apps, schema_editor):
    course_model = apps.get_model("courses", "Course")
    normalized_codes = set()
    for course in course_model.objects.all().only("id", "code"):
        normalized_code = course.code.strip().upper()
        if normalized_code in normalized_codes:
            raise RuntimeError(
                "Course codes collide after case-insensitive normalization."
            )
        normalized_codes.add(normalized_code)
        if course.code != normalized_code:
            course_model.objects.filter(pk=course.pk).update(code=normalized_code)


class Migration(migrations.Migration):
    dependencies = [("courses", "0002_course_teaching_assignment")]

    operations = [
        migrations.AlterField(
            model_name="course",
            name="code",
            field=models.CharField(max_length=50),
        ),
        migrations.RunPython(normalize_course_codes, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="course",
            constraint=models.UniqueConstraint(
                Lower("code"),
                name="course_unique_code_ci",
            ),
        ),
    ]
