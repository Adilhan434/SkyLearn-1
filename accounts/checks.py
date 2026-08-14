from django.core.checks import Error, Tags, register
from django.core.exceptions import ImproperlyConfigured

from accounts.oidc import OIDCConfiguration


@register(Tags.security)
def check_oidc_configuration(app_configs, **kwargs):
    del app_configs, kwargs
    configuration = OIDCConfiguration.from_settings()
    try:
        configuration.validate()
    except ImproperlyConfigured as exc:
        return [
            Error(
                str(exc),
                hint="Configure the OIDC_* environment variables or disable OIDC.",
                id="accounts.E001",
            )
        ]
    return []
