from bootstrap import setup_django

setup_django()

from accounts.models import User

try:
    user = User.objects.get(id=3)
    print(f"ID: 3, Username: {user.username}")
except User.DoesNotExist:
    print("User ID 3 not found")
except Exception as e:
    print(f"Error: {e}")
