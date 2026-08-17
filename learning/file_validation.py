from dataclasses import asdict, dataclass
import mimetypes
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

from learning.models import LearningMaterialType


class InvalidFileTypeError(ValidationError):
    """A material upload is empty, unsafe or does not match its declared type."""

    error_code = "invalid_file_type"


class FileTooLargeError(ValidationError):
    """A material upload exceeds the configured size limit."""

    error_code = "file_too_large"


EXECUTABLE_EXTENSIONS = {
    "apk",
    "app",
    "bat",
    "cgi",
    "cmd",
    "com",
    "deb",
    "dll",
    "dmg",
    "exe",
    "hta",
    "jar",
    "js",
    "lnk",
    "msi",
    "php",
    "pl",
    "ps1",
    "py",
    "reg",
    "rpm",
    "scr",
    "sh",
    "vbs",
}

EXTENSIONS_BY_TYPE = {
    LearningMaterialType.PDF: {"pdf"},
    LearningMaterialType.DOC: {"doc"},
    LearningMaterialType.DOCX: {"docx"},
    LearningMaterialType.PPT: {"ppt"},
    LearningMaterialType.PPTX: {"pptx"},
    LearningMaterialType.IMAGE: {"gif", "jpeg", "jpg", "png", "webp"},
    LearningMaterialType.AUDIO: {"flac", "m4a", "mp3", "ogg", "wav"},
    LearningMaterialType.VIDEO: {"m4v", "mov", "mp4", "ogv", "webm"},
    LearningMaterialType.OTHER: {"csv", "json", "md", "rtf", "txt", "xml"},
}

MIME_BY_EXTENSION = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "gif": "image/gif",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "flac": "audio/flac",
    "m4a": "audio/mp4",
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
    "wav": "audio/wav",
    "m4v": "video/mp4",
    "mov": "video/quicktime",
    "mp4": "video/mp4",
    "ogv": "video/ogg",
    "webm": "video/webm",
    "csv": "text/csv",
    "json": "application/json",
    "md": "text/markdown",
    "rtf": "application/rtf",
    "txt": "text/plain",
    "xml": "application/xml",
}


@dataclass(frozen=True)
class FileMetadata:
    original_filename: str
    mime_type: str
    size: int
    extension: str

    def as_model_fields(self):
        return asdict(self)


def _read_head(uploaded_file, length=8192):
    position = uploaded_file.tell()
    uploaded_file.seek(0)
    head = uploaded_file.read(length)
    uploaded_file.seek(position)
    return head


def _validate_double_extension(filename, extension):
    suffixes = [suffix.lower().lstrip(".") for suffix in Path(filename).suffixes]
    recognized = set().union(*EXTENSIONS_BY_TYPE.values(), EXECUTABLE_EXTENSIONS)
    if any(suffix in recognized for suffix in suffixes[:-1]):
        raise InvalidFileTypeError({"file": "Double extensions are not allowed."})
    if extension in EXECUTABLE_EXTENSIONS:
        raise InvalidFileTypeError({"file": "Executable file formats are not allowed."})


def _validate_office_zip(uploaded_file, extension):
    expected_member = {
        "docx": "word/document.xml",
        "pptx": "ppt/presentation.xml",
    }[extension]
    position = uploaded_file.tell()
    try:
        uploaded_file.seek(0)
        with ZipFile(uploaded_file) as archive:
            names = set(archive.namelist())
            if expected_member not in names:
                raise InvalidFileTypeError(
                    {"file": "Office document content does not match its extension."}
                )
            if any(item.flag_bits & 0x1 for item in archive.infolist()):
                raise InvalidFileTypeError(
                    {"file": "Encrypted office documents are not supported."}
                )
    except BadZipFile as exc:
        raise InvalidFileTypeError(
            {"file": "Office document is not a valid ZIP container."}
        ) from exc
    finally:
        uploaded_file.seek(position)


def _validate_image(uploaded_file, extension):
    expected_formats = {
        "gif": "GIF",
        "jpeg": "JPEG",
        "jpg": "JPEG",
        "png": "PNG",
        "webp": "WEBP",
    }
    position = uploaded_file.tell()
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as image:
            if image.format != expected_formats[extension]:
                raise InvalidFileTypeError(
                    {"file": "Image content does not match its extension."}
                )
            image.verify()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
        raise InvalidFileTypeError({"file": "Image content is invalid."}) from exc
    finally:
        uploaded_file.seek(position)


def _content_matches(extension, head):
    if extension == "pdf":
        return head.startswith(b"%PDF-")
    if extension in {"doc", "ppt"}:
        return head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if extension == "mp3":
        return head.startswith(b"ID3") or (
            len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0
        )
    if extension == "wav":
        return head.startswith(b"RIFF") and head[8:12] == b"WAVE"
    if extension == "flac":
        return head.startswith(b"fLaC")
    if extension in {"ogg", "ogv"}:
        return head.startswith(b"OggS")
    if extension in {"m4a", "m4v", "mov", "mp4"}:
        return len(head) >= 12 and head[4:8] == b"ftyp"
    if extension == "webm":
        return head.startswith(b"\x1a\x45\xdf\xa3")
    if extension == "rtf":
        return head.startswith(b"{\\rtf")
    if extension in {"csv", "json", "md", "txt", "xml"}:
        if b"\x00" in head:
            return False
        try:
            head.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return True
    return False


def _looks_executable(head):
    binary_signatures = (
        b"MZ",
        b"\x7fELF",
        b"\xca\xfe\xba\xbe",
        b"\xce\xfa\xed\xfe",
        b"\xcf\xfa\xed\xfe",
        b"\xfe\xed\xfa\xce",
        b"\xfe\xed\xfa\xcf",
    )
    stripped = head.lstrip()
    return head.startswith(binary_signatures) or stripped.startswith(b"#!")


def _validate_declared_mime(uploaded_file, detected_mime):
    declared_mime = getattr(uploaded_file, "content_type", "") or ""
    if declared_mime in {"", "application/octet-stream", detected_mime}:
        return
    guessed_mime, _encoding = mimetypes.guess_type(uploaded_file.name)
    if declared_mime == guessed_mime == detected_mime:
        return
    raise InvalidFileTypeError(
        {"file": "Declared MIME type does not match file content."}
    )


def validate_material_file(uploaded_file, material_type):
    """Validate an upload from bytes and return trusted metadata."""

    filename = Path(uploaded_file.name).name
    extension = Path(filename).suffix.lower().lstrip(".")
    size = uploaded_file.size
    if size == 0:
        raise InvalidFileTypeError({"file": "Empty files are not allowed."})
    if size > settings.MATERIAL_MAX_UPLOAD_SIZE:
        raise FileTooLargeError(
            {
                "file": (
                    "File exceeds the maximum upload size of "
                    f"{settings.MATERIAL_MAX_UPLOAD_SIZE_MB} MB."
                )
            }
        )

    _validate_double_extension(filename, extension)
    allowed_extensions = EXTENSIONS_BY_TYPE.get(material_type)
    if not allowed_extensions or extension not in allowed_extensions:
        raise InvalidFileTypeError(
            {"file": "File extension does not match the material type."}
        )

    head = _read_head(uploaded_file)
    if _looks_executable(head):
        raise InvalidFileTypeError({"file": "Executable file content is not allowed."})
    if extension in {"docx", "pptx"}:
        _validate_office_zip(uploaded_file, extension)
    elif extension in {"gif", "jpeg", "jpg", "png", "webp"}:
        _validate_image(uploaded_file, extension)
    elif not _content_matches(extension, head):
        raise InvalidFileTypeError(
            {"file": "File content does not match its extension."}
        )

    detected_mime = MIME_BY_EXTENSION[extension]
    _validate_declared_mime(uploaded_file, detected_mime)
    return FileMetadata(
        original_filename=filename,
        mime_type=detected_mime,
        size=size,
        extension=extension,
    )
