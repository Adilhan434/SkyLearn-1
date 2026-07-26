from bootstrap import setup_django

setup_django()

from accounts.models import User

try:
    user = User.objects.get(username='dilnaz')
    print(f"User: {user.username}")
    print(f"Is Active: {user.is_active}")
    print(f"Is Student: {user.is_student}")
    # We can't easily check password here without the cleartext, but we can check if it's set
    print(f"Has usable password: {user.has_usable_password()}")
except User.DoesNotExist:
    print("User 'dilnaz' not found")
except Exception as e:
    print(f"Error: {e}")
