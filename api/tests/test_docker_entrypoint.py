from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class DockerEntrypointTests(SimpleTestCase):
    def test_entrypoint_uses_linux_line_endings(self):
        entrypoint = Path(settings.BASE_DIR) / "docker-entrypoint.sh"

        self.assertNotIn(b"\r\n", entrypoint.read_bytes())
