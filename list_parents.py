import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import Parent

parents = Parent.objects.all()
for p in parents:
    print(f"Parent: {p.first_name} {p.last_name}, User: {p.user.username}, Phone: {p.phone}")
