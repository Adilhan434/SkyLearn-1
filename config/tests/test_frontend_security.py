from django.conf import settings
from django.test import SimpleTestCase


LOCAL_FRONTEND_ORIGIN = "http://localhost:5173"


class FrontendSecuritySettingsTests(SimpleTestCase):
    def test_local_frontend_is_explicitly_allowed(self):
        self.assertIn(LOCAL_FRONTEND_ORIGIN, settings.CORS_ALLOWED_ORIGINS)
        self.assertIn(LOCAL_FRONTEND_ORIGIN, settings.CSRF_TRUSTED_ORIGINS)

    def test_credentials_are_enabled_without_wildcard_origins(self):
        self.assertTrue(settings.CORS_ALLOW_CREDENTIALS)
        self.assertFalse(getattr(settings, "CORS_ALLOW_ALL_ORIGINS", False))
        self.assertNotIn("*", settings.CORS_ALLOWED_ORIGINS)

    def test_cors_middleware_runs_before_common_middleware(self):
        cors_index = settings.MIDDLEWARE.index(
            "corsheaders.middleware.CorsMiddleware"
        )
        common_index = settings.MIDDLEWARE.index(
            "django.middleware.common.CommonMiddleware"
        )
        self.assertLess(cors_index, common_index)
        self.assertEqual(settings.MIDDLEWARE.count(
            "django.middleware.common.CommonMiddleware"
        ), 1)

    def test_csrf_middleware_is_enabled(self):
        self.assertIn(
            "django.middleware.csrf.CsrfViewMiddleware",
            settings.MIDDLEWARE,
        )

    def test_jwt_cookie_security_defaults(self):
        self.assertTrue(settings.SIMPLE_JWT["AUTH_COOKIE_HTTP_ONLY"])
        self.assertEqual(settings.SIMPLE_JWT["AUTH_COOKIE_SAMESITE"], "Lax")
        self.assertIsInstance(
            settings.SIMPLE_JWT["AUTH_COOKIE_SECURE"], bool
        )

    def test_cors_preflight_returns_origin_and_credentials_headers(self):
        response = self.client.options(
            "/api/v1/auth/me/",
            HTTP_ORIGIN=LOCAL_FRONTEND_ORIGIN,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Access-Control-Allow-Origin"],
            LOCAL_FRONTEND_ORIGIN,
        )
        self.assertEqual(
            response["Access-Control-Allow-Credentials"],
            "true",
        )
