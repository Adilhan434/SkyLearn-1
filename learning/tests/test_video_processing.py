from io import BytesIO
import struct
from types import SimpleNamespace

from django.test import SimpleTestCase

from learning.models import LearningMaterialType
from learning.video_processing import (
    VideoProcessingService,
    parse_mp4_duration,
    probe_video_duration,
)


def box(box_type, payload, size=None):
    return struct.pack(">I4s", size or len(payload) + 8, box_type) + payload


class VideoDurationParserTests(SimpleTestCase):
    def parse(self, content, reported_size=None):
        return parse_mp4_duration(
            BytesIO(content),
            len(content) if reported_size is None else reported_size,
        )

    def test_reads_version_one_movie_header(self):
        header = b"\x01\x00\x00\x00" + struct.pack(">QQIQ", 0, 0, 1000, 7500)
        content = box(b"moov", box(b"mvhd", header))

        self.assertEqual(self.parse(content), 8)

    def test_returns_none_when_movie_or_movie_header_is_missing(self):
        samples = (
            box(b"ftyp", b"isom"),
            box(b"moov", box(b"free", b"metadata")),
        )

        for content in samples:
            with self.subTest(content=content):
                self.assertIsNone(self.parse(content))

    def test_rejects_truncated_or_invalid_boxes(self):
        samples = (
            (b"1234", 8),
            (struct.pack(">I4s", 1, b"moov"), 16),
            (box(b"moov", b"", size=4), None),
            (box(b"moov", box(b"mvhd", b"\x00")), None),
            (box(b"moov", box(b"mvhd", b"\x00\x00\x00\x00short")), None),
            (box(b"moov", box(b"mvhd", b"\x01\x00\x00\x00short")), None),
            (box(b"moov", box(b"mvhd", b"\x02\x00\x00\x00")), None),
        )

        for content, reported_size in samples:
            with self.subTest(content=content):
                self.assertIsNone(self.parse(content, reported_size))

    def test_zero_timescale_has_no_duration(self):
        header = b"\x00\x00\x00\x00" + struct.pack(">IIII", 0, 0, 0, 5000)
        content = box(b"moov", box(b"mvhd", header))

        self.assertIsNone(self.parse(content))

    def test_probe_ignores_unsupported_container(self):
        file_field = SimpleNamespace(name="lesson.webm")

        self.assertIsNone(probe_video_duration(file_field))

    def test_service_rejects_non_video_material(self):
        material = SimpleNamespace(type=LearningMaterialType.PDF, file=True)

        with self.assertRaisesMessage(ValueError, "requires a video"):
            VideoProcessingService().process(material)
