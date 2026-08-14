from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self) -> None:
        # Register drf-spectacular extensions.
        from .api import schema  # noqa: F401
        from . import checks  # noqa: F401
        from django.db.models.signals import (
            m2m_changed,
            post_delete,
            post_save,
            pre_save,
        )
        from .models import User, UserRole
        from .signals import (
            capture_legacy_role_flags,
            post_save_account_receiver,
            sync_flags_after_m2m_change,
            sync_flags_after_user_role_change,
            sync_roles_from_legacy_flags,
        )

        pre_save.connect(
            capture_legacy_role_flags,
            sender=User,
            dispatch_uid="accounts.capture_legacy_role_flags",
        )
        post_save.connect(
            post_save_account_receiver,
            sender=User,
            dispatch_uid="accounts.post_save_account",
        )
        post_save.connect(
            sync_roles_from_legacy_flags,
            sender=User,
            dispatch_uid="accounts.sync_roles_from_legacy_flags",
        )
        post_save.connect(
            sync_flags_after_user_role_change,
            sender=UserRole,
            dispatch_uid="accounts.sync_flags_after_user_role_save",
        )
        post_delete.connect(
            sync_flags_after_user_role_change,
            sender=UserRole,
            dispatch_uid="accounts.sync_flags_after_user_role_delete",
        )
        m2m_changed.connect(
            sync_flags_after_m2m_change,
            sender=User.roles.through,
            dispatch_uid="accounts.sync_flags_after_m2m_change",
        )

        return super().ready()
