import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.artifacts import TEMP_DIR_PREFIX, TextArtifact, VideoArtifact
from providers.youtube.resolver import YoutubeResolver


SHORTS_URL = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
CANONICAL_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


class YoutubeResolverTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.resolver = YoutubeResolver(
            max_duration_sec=600,
            max_filesize_bytes=1024,
        )
        self.download_dir = tempfile.mkdtemp(prefix=f"{TEMP_DIR_PREFIX}test_")
        self.addCleanup(self._cleanup_download_dir)

    def _cleanup_download_dir(self) -> None:
        if not os.path.isdir(self.download_dir):
            return
        for name in os.listdir(self.download_dir):
            os.unlink(os.path.join(self.download_dir, name))
        os.rmdir(self.download_dir)

    def _write_file(self, size: int) -> str:
        file_path = os.path.join(self.download_dir, "dQw4w9WgXcQ.mp4")
        with open(file_path, "wb") as video_file:
            video_file.write(b"x" * size)
        return file_path

    async def test_resolves_shorts_to_video_artifact(self) -> None:
        file_path = self._write_file(16)
        info = {"title": "Funny clip", "duration": 42}
        downloaded = dict(info, requested_downloads=[{"filepath": file_path}])

        with patch.object(
            YoutubeResolver, "_extract_info", return_value=info
        ), patch.object(
            YoutubeResolver, "_download", return_value=downloaded
        ), patch(
            "providers.youtube.resolver.tempfile.mkdtemp",
            return_value=self.download_dir,
        ):
            artifacts = await self.resolver.resolve(SHORTS_URL)

        self.assertEqual(len(artifacts), 1)
        artifact = artifacts[0]
        self.assertIsInstance(artifact, VideoArtifact)
        self.assertEqual(artifact.url, CANONICAL_URL)
        self.assertEqual(artifact.caption, "Funny clip")
        self.assertEqual(artifact.file_path, file_path)

    async def test_rejects_long_video_without_download(self) -> None:
        info = {"title": "Long talk", "duration": 3600}

        with patch.object(
            YoutubeResolver, "_extract_info", return_value=info
        ), patch.object(YoutubeResolver, "_download") as download_mock:
            artifacts = await self.resolver.resolve(CANONICAL_URL)

        download_mock.assert_not_called()
        self.assertEqual(len(artifacts), 1)
        artifact = artifacts[0]
        self.assertIsInstance(artifact, TextArtifact)
        self.assertEqual(artifact.title, "Long talk")
        self.assertEqual(artifact.post_url, CANONICAL_URL)
        self.assertIn("60:00", artifact.body)

    async def test_rejects_oversized_file_and_removes_it(self) -> None:
        file_path = self._write_file(2048)
        info = {"title": "Heavy", "duration": 100}
        downloaded = dict(info, requested_downloads=[{"filepath": file_path}])

        with patch.object(
            YoutubeResolver, "_extract_info", return_value=info
        ), patch.object(
            YoutubeResolver, "_download", return_value=downloaded
        ), patch(
            "providers.youtube.resolver.tempfile.mkdtemp",
            return_value=self.download_dir,
        ):
            artifacts = await self.resolver.resolve(CANONICAL_URL)

        self.assertFalse(os.path.exists(file_path))
        self.assertFalse(os.path.isdir(self.download_dir))
        self.assertEqual(len(artifacts), 1)
        self.assertIsInstance(artifacts[0], TextArtifact)

    async def test_removes_download_dir_when_no_file_produced(self) -> None:
        info = {"title": "Broken", "duration": 10}

        with patch.object(
            YoutubeResolver, "_extract_info", return_value=info
        ), patch.object(
            YoutubeResolver, "_download", return_value={}
        ), patch(
            "providers.youtube.resolver.tempfile.mkdtemp",
            return_value=self.download_dir,
        ):
            artifacts = await self.resolver.resolve(CANONICAL_URL)

        self.assertEqual(artifacts, [])
        self.assertFalse(os.path.isdir(self.download_dir))

    async def test_removes_download_dir_when_download_raises(self) -> None:
        info = {"title": "Broken", "duration": 10}
        self._write_file(8)

        with patch.object(
            YoutubeResolver, "_extract_info", return_value=info
        ), patch.object(
            YoutubeResolver, "_download", side_effect=RuntimeError("boom")
        ), patch(
            "providers.youtube.resolver.tempfile.mkdtemp",
            return_value=self.download_dir,
        ):
            with self.assertRaises(RuntimeError):
                await self.resolver.resolve(CANONICAL_URL)

        self.assertFalse(os.path.isdir(self.download_dir))

    async def test_ignores_non_video_url(self) -> None:
        artifacts = await self.resolver.resolve(
            "https://www.youtube.com/@channel"
        )
        self.assertEqual(artifacts, [])


if __name__ == "__main__":
    unittest.main()
