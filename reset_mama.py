import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User

try:
    user = User.objects.get(username='mama')
    user.set_password('123')
    user.save()
    print(f"Password for user '{user.username}' has been reset to '123'")
except User.DoesNotExist:
    print("User 'mama' not found")
except Exception as e:
    print(f"Error: {e}")
