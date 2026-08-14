from pathlib import Path


STATICFILES_BACKEND = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)


def build_storage_config(
    *,
    use_s3=False,
    endpoint_url="",
    access_key="",
    secret_key="",
    bucket="",
    region="",
    location="media",
    addressing_style="path",
    querystring_expire=300,
):
    """Build Django STORAGES for local media or an S3-compatible service."""

    staticfiles = {"BACKEND": STATICFILES_BACKEND}
    if not use_s3:
        return {
            "default": {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
            },
            "staticfiles": staticfiles,
        }

    if not bucket:
        raise ValueError("S3_BUCKET is required when USE_S3=True.")
    if addressing_style not in {"path", "virtual"}:
        raise ValueError("S3_ADDRESSING_STYLE must be path or virtual.")
    if querystring_expire < 1:
        raise ValueError("S3_QUERYSTRING_EXPIRE must be positive.")

    options = {
        "bucket_name": bucket,
        "default_acl": None,
        "file_overwrite": False,
        "querystring_auth": True,
        "querystring_expire": querystring_expire,
        "signature_version": "s3v4",
        "addressing_style": addressing_style,
        "location": location.strip("/"),
    }
    optional_options = {
        "endpoint_url": endpoint_url,
        "access_key": access_key,
        "secret_key": secret_key,
        "region_name": region,
    }
    options.update(
        {
            key: value
            for key, value in optional_options.items()
            if value
        }
    )
    return {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": options,
        },
        "staticfiles": staticfiles,
    }


def local_media_root(base_dir):
    return str(Path(base_dir) / "media")
