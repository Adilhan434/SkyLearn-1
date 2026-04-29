from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0003_user_is_methodologist'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('document_type', models.CharField(choices=[('certificate', 'Certificate of Enrollment'), ('transcript', 'Academic Transcript'), ('reference', 'Reference Letter'), ('military', 'Military Reference'), ('other', 'Other')], max_length=30)),
                ('description', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('pending', 'Pending Review'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('methodologist_note', models.TextField(blank=True, default='')),
                ('approved_file', models.FileField(blank=True, null=True, upload_to='documents/approved/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_documents', to=settings.AUTH_USER_MODEL)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='document_requests', to='accounts.student')),
            ],
            options={
                'verbose_name': 'Document Request',
                'verbose_name_plural': 'Document Requests',
                'ordering': ['-created_at'],
            },
        ),
    ]
