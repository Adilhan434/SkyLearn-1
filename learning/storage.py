from django.core.files.storage import storages


def material_storage():
    """Resolve the private backend without coupling models to local or S3."""

    return storages["private"]
