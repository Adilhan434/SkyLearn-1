from bootstrap import setup_django

setup_django()

from accounts.models import Parent

parents = Parent.objects.all()
for p in parents:
    print(f"Parent: {p.first_name} {p.last_name}, User: {p.user.username}, Phone: {p.phone}")
