from django.core.checks import run_checks
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from accounts.oidc import OIDCConfiguration, OIDCService


DISABLED_OIDC = {
    "OIDC_ENABLED": False,
    "OIDC_ISSUER_URL": "",
    "OIDC_CLIENT_ID": "",
    "OIDC_CLIENT_SECRET": "",
    "OIDC_REDIRECT_URI": "",
}

ENABLED_OIDC = {
    "OIDC_ENABLED": True,
    "OIDC_ISSUER_URL": "https://identity.example.edu/",
    "OIDC_CLIENT_ID": "su-lms",
    "OIDC_CLIENT_SECRET": "test-secret",
    "OIDC_REDIRECT_URI": "https://lms.example.edu/api/v1/auth/oidc/callback/",
}


class OIDCArchitectureTests(SimpleTestCase):
    @override_settings(**DISABLED_OIDC)
    def test_disabled_oidc_does_not_require_provider_credentials(self):
        service = OIDCService()

        service.validate_configuration()

        self.assertFalse(service.is_ready)
        self.assertFalse(
            [
                error
                for error in run_checks(tags=["security"])
                if error.id == "accounts.E001"
            ]
        )

    @override_settings(**ENABLED_OIDC)
    def test_enabled_oidc_exposes_provider_neutral_flow_parameters(self):
        service = OIDCService()

        parameters = service.authorization_request_parameters(
            state="state-value",
            nonce="nonce-value",
            code_challenge="challenge-value",
        )

        self.assertTrue(service.is_ready)
        self.assertEqual(
            service.discovery_url(),
            "https://identity.example.edu/.well-known/openid-configuration",
        )
        self.assertEqual(parameters["response_type"], "code")
        self.assertEqual(parameters["scope"], "openid profile email")
        self.assertEqual(parameters["code_challenge_method"], "S256")
        self.assertNotIn("client_secret", parameters)

    @override_settings(**{**DISABLED_OIDC, "OIDC_ENABLED": True})
    def test_enabled_oidc_reports_missing_environment_settings(self):
        service = OIDCService()

        self.assertFalse(service.is_ready)
        with self.assertRaises(ImproperlyConfigured):
            service.validate_configuration()

        errors = [
            error
            for error in run_checks(tags=["security"])
            if error.id == "accounts.E001"
        ]
        self.assertEqual(len(errors), 1)
        self.assertIn("OIDC_CLIENT_SECRET", errors[0].msg)

    @override_settings(**{**ENABLED_OIDC, "OIDC_ISSUER_URL": "provider.local"})
    def test_enabled_oidc_rejects_non_absolute_provider_urls(self):
        configuration = OIDCConfiguration.from_settings()

        with self.assertRaises(ImproperlyConfigured):
            configuration.validate()

    @override_settings(**ENABLED_OIDC)
    def test_authorization_request_requires_state_and_nonce(self):
        service = OIDCService()

        with self.assertRaises(ValueError):
            service.authorization_request_parameters(state="", nonce="nonce")
