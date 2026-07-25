from .models import Role, RoleCode, User, UserRole
from .utils import (
    generate_student_credentials,
    generate_lecturer_credentials,
    send_new_account_email,
)

LEGACY_ROLE_FIELDS = {
    "is_student": RoleCode.STUDENT,
    "is_lecturer": RoleCode.TEACHER,
    "is_superuser": RoleCode.SUPER_ADMIN,
}


def capture_legacy_role_flags(instance, raw=False, **kwargs):
    if raw or not instance.pk:
        instance._previous_legacy_role_flags = None
        return

    instance._previous_legacy_role_flags = (
        User.objects.filter(pk=instance.pk)
        .values(*LEGACY_ROLE_FIELDS)
        .first()
    )


def sync_roles_from_legacy_flags(instance, raw=False, **kwargs):
    if raw:
        return

    previous = getattr(instance, "_previous_legacy_role_flags", None)
    for field_name, role_code in LEGACY_ROLE_FIELDS.items():
        current_value = bool(getattr(instance, field_name))
        previous_value = (
            bool(previous[field_name]) if previous is not None else False
        )
        if current_value == previous_value:
            continue

        role, _ = Role.objects.get_or_create(
            code=role_code,
            defaults={"name": RoleCode(role_code).label},
        )
        if current_value:
            UserRole.objects.get_or_create(user=instance, role=role)
        else:
            UserRole.objects.filter(user=instance, role=role).delete()


def sync_legacy_flags_from_roles(user_id):
    role_codes = set(
        UserRole.objects.filter(user_id=user_id).values_list(
            "role__code", flat=True
        )
    )
    updates = {
        field_name: role_code in role_codes
        for field_name, role_code in LEGACY_ROLE_FIELDS.items()
    }
    User.objects.filter(pk=user_id).update(**updates)


def sync_flags_after_user_role_change(instance, **kwargs):
    sync_legacy_flags_from_roles(instance.user_id)


def sync_flags_after_m2m_change(
    sender,
    instance,
    action,
    reverse,
    pk_set,
    **kwargs,
):
    if action == "pre_clear" and reverse:
        instance._legacy_sync_user_ids = list(
            instance.users.values_list("pk", flat=True)
        )
        return

    if action not in {"post_add", "post_remove", "post_clear"}:
        return

    if reverse:
        user_ids = pk_set or getattr(instance, "_legacy_sync_user_ids", [])
    else:
        user_ids = [instance.pk]

    for user_id in user_ids:
        sync_legacy_flags_from_roles(user_id)


def post_save_account_receiver(instance=None, created=False, *args, **kwargs):
    """
    Send email notification
    """
    if created:
        if instance.is_student:
            username, password = generate_student_credentials()
            instance.username = username
            instance.set_password(password)
            instance.save()
            # Send email with the generated credentials
            send_new_account_email(instance, password)

        if instance.is_lecturer:
            username, password = generate_lecturer_credentials()
            instance.username = username
            instance.set_password(password)
            instance.save()
            # Send email with the generated credentials
            send_new_account_email(instance, password)
