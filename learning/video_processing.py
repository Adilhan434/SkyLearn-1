import struct

from learning.models import LearningMaterialType, VideoProcessingStatus


def _read_box_header(stream, offset, end):
    if offset + 8 > end:
        return None
    stream.seek(offset)
    header = stream.read(8)
    if len(header) != 8:
        return None
    size, box_type = struct.unpack(">I4s", header)
    header_size = 8
    if size == 1:
        extended_size = stream.read(8)
        if len(extended_size) != 8:
            return None
        size = struct.unpack(">Q", extended_size)[0]
        header_size = 16
    elif size == 0:
        size = end - offset
    if size < header_size or offset + size > end:
        return None
    return box_type, offset + header_size, offset + size


def _find_box(stream, box_type, start, end):
    offset = start
    while offset < end:
        box = _read_box_header(stream, offset, end)
        if box is None:
            return None
        current_type, payload_start, box_end = box
        if current_type == box_type:
            return payload_start, box_end
        offset = box_end
    return None


def parse_mp4_duration(stream, size):
    moov = _find_box(stream, b"moov", 0, size)
    if moov is None:
        return None
    mvhd = _find_box(stream, b"mvhd", *moov)
    if mvhd is None:
        return None
    payload_start, payload_end = mvhd
    stream.seek(payload_start)
    version_bytes = stream.read(4)
    if len(version_bytes) != 4:
        return None
    version = version_bytes[0]
    if version == 0:
        values = stream.read(16)
        if len(values) != 16:
            return None
        _created, _modified, timescale, duration = struct.unpack(">IIII", values)
    elif version == 1:
        values = stream.read(28)
        if len(values) != 28:
            return None
        _created, _modified, timescale, duration = struct.unpack(">QQIQ", values)
    else:
        return None
    if not timescale or stream.tell() > payload_end:
        return None
    return (duration + timescale // 2) // timescale


def probe_video_duration(file_field):
    """Return video duration in whole seconds when the container is supported."""

    if not file_field or file_field.name.rsplit(".", 1)[-1].lower() not in {
        "m4v",
        "mov",
        "mp4",
    }:
        return None
    with file_field.open("rb") as stream:
        return parse_mp4_duration(stream, file_field.size)


class VideoProcessingService:
    """Synchronous Release 1 interface replaceable by an async transcoder."""

    def process(self, material):
        if material.type != LearningMaterialType.VIDEO or not material.file:
            raise ValueError("Video processing requires a video material file.")
        self._save_state(material, VideoProcessingStatus.PROCESSING, None)
        try:
            duration = probe_video_duration(material.file)
        except (OSError, ValueError):
            self._save_state(material, VideoProcessingStatus.FAILED, None)
            return material
        self._save_state(material, VideoProcessingStatus.READY, duration)
        return material

    @staticmethod
    def _save_state(material, status, duration):
        material.video_status = status
        material.duration_seconds = duration
        material.save(
            update_fields=(
                "video_status",
                "duration_seconds",
                "updated_at",
            )
        )
