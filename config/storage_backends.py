from django.core.files.storage import FileSystemStorage
from storages.backends.s3 import S3Storage


PRIVATE_URL_ERROR = "Private files are available only through protected API endpoints."


class PrivateFileSystemStorage(FileSystemStorage):
    def url(self, name):
        del name
        raise ValueError(PRIVATE_URL_ERROR)


class PrivateS3Storage(S3Storage):
    def url(self, name, parameters=None, expire=None, http_method=None):
        del name, parameters, expire, http_method
        raise ValueError(PRIVATE_URL_ERROR)
