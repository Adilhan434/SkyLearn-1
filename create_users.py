import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

roles = [
    ('admin@admin.com', 'admin', 'admin', 'admin'),
    ('teacher@teacher.com', 'teacher', 'teacher', 'teacher'),
    ('student@student.com', 'student', 'student', 'student'),
    ('accountant@accountant.com', 'accountant', 'accountant', 'accountant'),
    ('parent@parent.com', 'parent', 'parent', 'parent'),
    ('methodologist@methodologist.com', 'methodologist', 'methodologist', 'methodologist'),
]

for email, first, last, role in roles:
    if not User.objects.filter(email=email).exists():
        u = User.objects.create_user(username=email, email=email, password='password123', first_name=first, last_name=last)
        if role == 'admin':
            u.is_staff = True
            u.is_superuser = True
        elif role == 'teacher':
            u.is_lecturer = True
        elif role == 'student':
            u.is_student = True
        elif role == 'accountant':
            u.is_accountant = True
        elif role == 'parent':
            u.is_parent = True
        elif role == 'methodologist':
            u.is_methodologist = True
        u.save()
        print(f'Created {role}: {email} / password123')
    else:
        u = User.objects.get(email=email)
        u.set_password('password123')
        u.save()
        print(f'Reset {role}: {email} / password123')
