from pathlib import Path

from django.core.files.storage import FileSystemStorage, storages
from django.core.files.storage.handler import StorageHandler
from django.test import SimpleTestCase, override_settings

from config.storage import build_storage_config, local_media_root


class StorageConfigTests(SimpleTestCase):
    def test_local_storage_is_the_default(self):
        storage_config = build_storage_config()

        self.assertEqual(
            storage_config["default"],
            {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        )
        self.assertEqual(
            storage_config["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )

    @override_settings(STORAGES=build_storage_config())
    def test_local_backend_uses_django_file_storage_interface(self):
        self.assertIsInstance(storages["default"], FileSystemStorage)

    def test_s3_storage_maps_compatible_service_options(self):
        storage_config = build_storage_config(
            use_s3=True,
            endpoint_url="http://minio:9000",
            access_key="test-access-key",
            secret_key="test-secret-key",
            bucket="su-lms-media",
            region="us-east-1",
            location="private/media/",
            addressing_style="path",
            querystring_expire=120,
        )

        self.assertEqual(
            storage_config["default"]["BACKEND"],
            "storages.backends.s3.S3Storage",
        )
        self.assertEqual(
            storage_config["default"]["OPTIONS"],
            {
                "bucket_name": "su-lms-media",
                "default_acl": None,
                "file_overwrite": False,
                "querystring_auth": True,
                "querystring_expire": 120,
                "signature_version": "s3v4",
                "addressing_style": "path",
                "location": "private/media",
                "endpoint_url": "http://minio:9000",
                "access_key": "test-access-key",
                "secret_key": "test-secret-key",
                "region_name": "us-east-1",
            },
        )

    def test_s3_backend_uses_django_storage_interface(self):
        storage_config = build_storage_config(
            use_s3=True,
            endpoint_url="http://minio:9000",
            access_key="test-access-key",
            secret_key="test-secret-key",
            bucket="su-lms-media",
            region="us-east-1",
        )

        storage = StorageHandler(storage_config)["default"]

        self.assertEqual(storage.__class__.__name__, "S3Storage")
        self.assertEqual(storage.bucket_name, "su-lms-media")
        self.assertEqual(storage.endpoint_url, "http://minio:9000")
        self.assertTrue(storage.querystring_auth)

    def test_s3_allows_runtime_iam_credentials(self):
        options = build_storage_config(
            use_s3=True,
            bucket="su-lms-media",
        )["default"]["OPTIONS"]

        self.assertNotIn("access_key", options)
        self.assertNotIn("secret_key", options)

    def test_s3_requires_bucket(self):
        with self.assertRaisesMessage(ValueError, "S3_BUCKET"):
            build_storage_config(use_s3=True)

    def test_s3_rejects_invalid_addressing_style(self):
        with self.assertRaisesMessage(ValueError, "S3_ADDRESSING_STYLE"):
            build_storage_config(
                use_s3=True,
                bucket="su-lms-media",
                addressing_style="invalid",
            )

    def test_s3_rejects_non_positive_url_expiry(self):
        with self.assertRaisesMessage(ValueError, "S3_QUERYSTRING_EXPIRE"):
            build_storage_config(
                use_s3=True,
                bucket="su-lms-media",
                querystring_expire=0,
            )

    def test_local_media_root_is_platform_independent(self):
        root = local_media_root(Path("project"))

        self.assertEqual(Path(root), Path("project") / "media")
