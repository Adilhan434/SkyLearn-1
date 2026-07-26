from django.conf import settings


def _cookie_settings():
    return {
        "httponly": settings.SIMPLE_JWT.get("AUTH_COOKIE_HTTP_ONLY", True),
        "secure": settings.SIMPLE_JWT.get("AUTH_COOKIE_SECURE", not settings.DEBUG),
        "samesite": settings.SIMPLE_JWT.get("AUTH_COOKIE_SAMESITE", "Lax"),
        "domain": settings.SIMPLE_JWT.get("AUTH_COOKIE_DOMAIN"),
        "path": settings.SIMPLE_JWT.get("AUTH_COOKIE_PATH", "/"),
    }


def set_access_cookie(response, token):
    response.set_cookie(
        key=settings.SIMPLE_JWT.get("AUTH_COOKIE", "access_token"),
        value=str(token),
        max_age=int(
            settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()
        ),
        **_cookie_settings(),
    )


def set_refresh_cookie(response, token):
    response.set_cookie(
        key=settings.SIMPLE_JWT.get("AUTH_COOKIE_REFRESH", "refresh_token"),
        value=str(token),
        max_age=int(
            settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()
        ),
        **_cookie_settings(),
    )


def clear_auth_cookies(response):
    cookie_settings = _cookie_settings()
    delete_options = {
        "path": cookie_settings["path"],
        "domain": cookie_settings["domain"],
        "samesite": cookie_settings["samesite"],
    }
    response.delete_cookie(
        settings.SIMPLE_JWT.get("AUTH_COOKIE", "access_token"),
        **delete_options,
    )
    response.delete_cookie(
        settings.SIMPLE_JWT.get("AUTH_COOKIE_REFRESH", "refresh_token"),
        **delete_options,
    )
