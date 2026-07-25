# Compatibility migration.
#
# Lecturer is already created by 0001_initial in this repository. Keeping a
# second CreateModel operation makes a clean `migrate` fail with
# "table accounts_lecturer already exists".

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_user_first_name_alter_user_last_name"),
    ]

    operations = []
