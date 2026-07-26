from bootstrap import setup_django

setup_django()

from django.contrib.auth import authenticate

user = authenticate(username='dilnaz', password='123')
if user:
    print(f"Authentication SUCCESS for user: {user.username}")
else:
    print("Authentication FAILED")
