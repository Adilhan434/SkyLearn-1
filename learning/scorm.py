from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from django.conf import settings
from django.core.exceptions import ValidationError


MAX_MANIFEST_SIZE = 2 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100


@dataclass(frozen=True)
class ScormMetadata:
    version: str
    launch_path: str


def normalize_member_path(name):
    normalized_name = unquote(name).replace("\\", "/")
    path = PurePosixPath(normalized_name)
    if (
        not normalized_name
        or normalized_name.startswith("/")
        or path.is_absolute()
        or ".." in path.parts
        or any(":" in part for part in path.parts)
        or any(ord(character) < 32 for character in normalized_name)
    ):
        raise ValidationError({"file": "SCORM package contains an unsafe path."})
    normalized_path = path.as_posix()
    if normalized_path in {"", "."}:
        raise ValidationError({"file": "SCORM package contains an unsafe path."})
    return normalized_path


def _validate_archive_members(archive):
    members = archive.infolist()
    if len(members) > settings.SCORM_MAX_FILES:
        raise ValidationError({"file": "SCORM package contains too many files."})
    names = {}
    total_size = 0
    total_compressed = 0
    for member in members:
        normalized = normalize_member_path(member.filename)
        normalized_key = normalized.casefold()
        if normalized_key in names:
            raise ValidationError(
                {"file": "SCORM package contains duplicate file paths."}
            )
        names[normalized_key] = member
        if member.flag_bits & 0x1:
            raise ValidationError(
                {"file": "Encrypted SCORM packages are not supported."}
            )
        total_size += member.file_size
        total_compressed += member.compress_size
    if total_size > settings.SCORM_MAX_UNCOMPRESSED_SIZE:
        raise ValidationError(
            {"file": "SCORM package is too large after decompression."}
        )
    if total_size and (
        not total_compressed or total_size / total_compressed > MAX_COMPRESSION_RATIO
    ):
        raise ValidationError({"file": "SCORM package compression ratio is unsafe."})
    return names


def _local_name(value):
    return value.rsplit("}", 1)[-1].lower()


def _manifest_metadata(manifest_content, members):
    upper_content = manifest_content.upper()
    if b"<!DOCTYPE" in upper_content or b"<!ENTITY" in upper_content:
        raise ValidationError(
            {"file": "SCORM manifest contains forbidden XML declarations."}
        )
    try:
        root = ElementTree.fromstring(manifest_content)
    except ElementTree.ParseError as exc:
        raise ValidationError({"file": "SCORM manifest XML is invalid."}) from exc

    version = "unknown"
    resources = []
    for element in root.iter():
        local_name = _local_name(element.tag)
        if local_name == "schemaversion" and element.text:
            version = element.text.strip()[:50] or "unknown"
        elif local_name == "resource" and element.get("href"):
            resources.append(element)
    if not resources:
        raise ValidationError(
            {"file": "SCORM manifest does not define a launch resource."}
        )
    resources.sort(
        key=lambda item: not any(
            _local_name(key) == "scormtype" and value.lower() == "sco"
            for key, value in item.attrib.items()
        )
    )
    raw_path = urlsplit(resources[0].get("href")).path
    launch_path = normalize_member_path(raw_path)
    matching_member = members.get(launch_path.casefold())
    if matching_member is None or matching_member.is_dir():
        raise ValidationError(
            {"file": "SCORM launch resource is missing from the package."}
        )
    return ScormMetadata(
        version=version,
        launch_path=normalize_member_path(matching_member.filename),
    )


def validate_scorm_package(uploaded_file):
    """Validate a SCORM ZIP and return trusted manifest metadata."""

    if not uploaded_file.name.lower().endswith(".zip"):
        raise ValidationError({"file": "SCORM package must be a ZIP file."})
    if uploaded_file.size == 0:
        raise ValidationError({"file": "SCORM package cannot be empty."})
    if uploaded_file.size > settings.MATERIAL_MAX_UPLOAD_SIZE:
        raise ValidationError({"file": "SCORM package exceeds the upload limit."})

    position = uploaded_file.tell()
    try:
        uploaded_file.seek(0)
        with ZipFile(uploaded_file) as archive:
            members = _validate_archive_members(archive)
            manifest_member = members.get("imsmanifest.xml")
            if manifest_member is None or manifest_member.is_dir():
                raise ValidationError(
                    {"file": "SCORM package must contain imsmanifest.xml."}
                )
            if manifest_member.file_size > MAX_MANIFEST_SIZE:
                raise ValidationError({"file": "SCORM manifest is too large."})
            manifest_content = archive.read(manifest_member)
            return _manifest_metadata(manifest_content, members)
    except BadZipFile as exc:
        raise ValidationError(
            {"file": "SCORM package is not a valid ZIP file."}
        ) from exc
    finally:
        uploaded_file.seek(position)


def stream_scorm_member(file_field, requested_path, chunk_size=64 * 1024):
    """Open one validated member and return a bounded-memory byte iterator."""

    normalized_path = normalize_member_path(requested_path)
    stored_file = file_field.open("rb")
    archive = None
    try:
        archive = ZipFile(stored_file)
        members = _validate_archive_members(archive)
        member = members.get(normalized_path.casefold())
        if member is None or member.is_dir():
            raise KeyError(normalized_path)
        member_stream = archive.open(member)
    except (BadZipFile, KeyError, OSError, RuntimeError, ValidationError):
        if archive is not None:
            archive.close()
        stored_file.close()
        raise

    def chunks():
        try:
            while True:
                chunk = member_stream.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            member_stream.close()
            archive.close()
            stored_file.close()

    return chunks(), normalized_path
