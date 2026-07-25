import django_filters

from accounts.models import User


class UserFilter(django_filters.FilterSet):
    role = django_filters.CharFilter(
        field_name="roles__code",
        lookup_expr="exact",
    )
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = User
        fields = ["role", "is_active"]
