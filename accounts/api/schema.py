from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class JWTCookieAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "accounts.authentication.JWTCookieAuthentication"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.SIMPLE_JWT.get("AUTH_COOKIE", "access_token"),
            "description": "JWT access token stored in an httpOnly cookie.",
        }
