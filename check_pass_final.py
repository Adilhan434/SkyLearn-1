import os
import django
from django.contrib.auth.hashers import check_password

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User

try:
    user = User.objects.get(username='dilnaz')
    password_to_check = '123'
    match = user.check_password(password_to_check)
    print(f"User: {user.username}")
    print(f"Password '123' match: {match}")
    print(f"Password hash: {user.password}")
except User.DoesNotExist:
    print("User 'dilnaz' not found")
except Exception as e:
    print(f"Error: {e}")
