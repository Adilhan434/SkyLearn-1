from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("enrollments", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="enrollment",
            constraint=models.UniqueConstraint(
                fields=("student", "course"),
                name="enrollment_unique_student_course",
            ),
        ),
    ]
