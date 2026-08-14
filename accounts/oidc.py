from dataclasses import dataclass, field
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class OIDCConfiguration:
    """Provider-neutral OpenID Connect client configuration."""

    enabled: bool
    issuer_url: str
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str

    @classmethod
    def from_settings(cls):
        return cls(
            enabled=settings.OIDC_ENABLED,
            issuer_url=settings.OIDC_ISSUER_URL.strip(),
            client_id=settings.OIDC_CLIENT_ID.strip(),
            client_secret=settings.OIDC_CLIENT_SECRET.strip(),
            redirect_uri=settings.OIDC_REDIRECT_URI.strip(),
        )

    def missing_settings(self):
        values = {
            "OIDC_ISSUER_URL": self.issuer_url,
            "OIDC_CLIENT_ID": self.client_id,
            "OIDC_CLIENT_SECRET": self.client_secret,
            "OIDC_REDIRECT_URI": self.redirect_uri,
        }
        return tuple(name for name, value in values.items() if not value)

    @staticmethod
    def _is_http_url(value):
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def validate(self):
        if not self.enabled:
            return
        missing = self.missing_settings()
        if missing:
            raise ImproperlyConfigured(
                "OIDC is enabled but required settings are missing: "
                + ", ".join(missing)
            )
        invalid_urls = [
            name
            for name, value in (
                ("OIDC_ISSUER_URL", self.issuer_url),
                ("OIDC_REDIRECT_URI", self.redirect_uri),
            )
            if not self._is_http_url(value)
        ]
        if invalid_urls:
            raise ImproperlyConfigured(
                "OIDC settings must be absolute HTTP(S) URLs: "
                + ", ".join(invalid_urls)
            )


class OIDCService:
    """OIDC integration boundary awaiting a concrete university provider."""

    def __init__(self, configuration=None):
        self.configuration = configuration or OIDCConfiguration.from_settings()

    @property
    def is_ready(self):
        if not self.configuration.enabled:
            return False
        try:
            self.configuration.validate()
        except ImproperlyConfigured:
            return False
        return True

    def validate_configuration(self):
        self.configuration.validate()

    def discovery_url(self):
        self.validate_configuration()
        return (
            self.configuration.issuer_url.rstrip("/")
            + "/.well-known/openid-configuration"
        )

    def authorization_request_parameters(self, *, state, nonce, code_challenge=None):
        """Return provider-neutral Authorization Code Flow parameters."""
        self.validate_configuration()
        if not state or not nonce:
            raise ValueError("OIDC state and nonce are required.")
        parameters = {
            "client_id": self.configuration.client_id,
            "redirect_uri": self.configuration.redirect_uri,
            "response_type": "code",
            "scope": "openid profile email",
            "state": state,
            "nonce": nonce,
        }
        if code_challenge:
            parameters.update(
                {
                    "code_challenge": code_challenge,
                    "code_challenge_method": "S256",
                }
            )
        return parameters
