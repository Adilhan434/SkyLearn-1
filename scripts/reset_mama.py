from bootstrap import setup_django

setup_django()

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
