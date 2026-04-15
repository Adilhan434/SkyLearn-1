from rest_framework.throttling import AnonRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    """Strict throttle for authentication endpoints (login, token refresh)."""
    scope = 'auth'
