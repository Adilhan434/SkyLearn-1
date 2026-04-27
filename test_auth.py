import os
import django
from django.contrib.auth import authenticate

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

user = authenticate(username='dilnaz', password='123')
if user:
    print(f"Authentication SUCCESS for user: {user.username}")
else:
    print("Authentication FAILED")
