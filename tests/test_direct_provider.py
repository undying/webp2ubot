import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.artifacts import ImageArtifact, VideoArtifact
from providers.direct.provider import DirectProvider, MediaType


PAYLOAD = b"not a real image"


def _webp_payload() -> bytes:
    import io as _io

    import PIL.Image

    buffer = _io.BytesIO()
    PIL.Image.new("RGB", (4, 4), (255, 0, 0)).save(buffer, "WEBP")
    return buffer.getvalue()


class DirectProviderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.provider = DirectProvider()

    async def test_unsupported_content_type_resolves_nothing(self) -> None:
        with patch.object(
            DirectProvider, "_detect_content_type", return_value=None
        ):
            self.assertEqual(
                await self.provider.resolve("https://example.com/page"),
                [],
            )

    async def test_image_resolves_to_file_artifact(self) -> None:
        with patch.object(
            DirectProvider, "_download", return_value=_webp_payload()
        ):
            artifacts = await self.provider.resolve(
                "https://example.com/meme.webp"
            )

        self.assertEqual(len(artifacts), 1)
        artifact = artifacts[0]
        self.assertIsInstance(artifact, ImageArtifact)
        self.addCleanup(os.unlink, artifact.file_path)
        self.assertTrue(artifact.file_path.endswith(".jpg"))

    async def test_video_resolves_to_file_artifact(self) -> None:
        with patch.object(
            DirectProvider, "_download", return_value=PAYLOAD
        ), patch.object(
            DirectProvider,
            "_convert",
            return_value="/tmp/converted.mp4",
        ):
            artifacts = await self.provider.resolve(
                "https://example.com/clip.webm"
            )

        self.assertEqual(len(artifacts), 1)
        self.assertIsInstance(artifacts[0], VideoArtifact)

    def test_convert_leaves_no_orphan_temp_file(self) -> None:
        tmp_root = Path(os.environ.get("TMPDIR", "/tmp"))
        before = set(tmp_root.glob("*.jpg"))

        with patch(
            "providers.direct.provider.PIL.Image.open",
            side_effect=ValueError("broken image"),
        ):
            with self.assertRaises(ValueError):
                DirectProvider._convert(PAYLOAD, "image/webp", MediaType.IMAGE)

        self.assertEqual(set(tmp_root.glob("*.jpg")) - before, set())


if __name__ == "__main__":
    unittest.main()
