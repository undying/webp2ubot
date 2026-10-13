import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.artifacts import (
    GalleryArtifact,
    ImageArtifact,
    TEMP_DIR_PREFIX,
    TextArtifact,
    VideoArtifact,
)
from providers.instagram.resolver import InstagramResolver


REEL_URL = "https://www.instagram.com/reels/C9aBcDeFgHi/?igsh=abc"
POST_URL = "https://www.instagram.com/reel/C9aBcDeFgHi/"


def _video_entry(duration: int = 10) -> dict:
    return {
        "formats": [{"url": "https://cdn/video.mp4"}],
        "duration": duration,
        "thumbnails": [{"url": "https://cdn/small.jpg"}],
    }


def _image_entry(url: str) -> dict:
    return {
        "formats": [],
        "thumbnails": [
            {"url": f"{url}?small"},
            {"url": url},
        ],
    }


class InstagramResolverTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.resolver = InstagramResolver(
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

    def _write_file(self, size: int, name: str = "video.mp4") -> str:
        file_path = os.path.join(self.download_dir, name)
        with open(file_path, "wb") as video_file:
            video_file.write(b"x" * size)
        return file_path

    def _patches(self, info: dict, downloaded: dict):
        return (
            patch.object(
                InstagramResolver, "_extract_info", return_value=info
            ),
            patch.object(
                InstagramResolver, "_download", return_value=downloaded
            ),
            patch(
                "providers.instagram.resolver.tempfile.mkdtemp",
                return_value=self.download_dir,
            ),
        )

    async def test_resolves_reel_to_video_artifact(self) -> None:
        file_path = self._write_file(16)
        info = dict(_video_entry(), description="Funny clip")
        downloaded = {"requested_downloads": [{"filepath": file_path}]}

        extract, download, mkdtemp = self._patches(info, downloaded)
        with extract, download, mkdtemp:
            artifacts = await self.resolver.resolve(REEL_URL)

        self.assertEqual(len(artifacts), 1)
        artifact = artifacts[0]
        self.assertIsInstance(artifact, VideoArtifact)
        self.assertEqual(artifact.url, POST_URL)
        self.assertEqual(artifact.caption, "Funny clip")
        self.assertEqual(artifact.file_path, file_path)

    async def test_resolves_photo_post_to_image_artifact(self) -> None:
        info = dict(
            _image_entry("https://cdn/photo.jpg"),
            description="Nice shot",
        )

        with patch.object(
            InstagramResolver, "_extract_info", return_value=info
        ), patch.object(InstagramResolver, "_download") as download_mock:
            artifacts = await self.resolver.resolve(POST_URL)

        download_mock.assert_not_called()
        self.assertEqual(len(artifacts), 1)
        artifact = artifacts[0]
        self.assertIsInstance(artifact, ImageArtifact)
        self.assertEqual(artifact.url, "https://cdn/photo.jpg")
        self.assertEqual(artifact.caption, "Nice shot")

    async def test_resolves_carousel_to_video_and_gallery(self) -> None:
        file_path = self._write_file(16)
        info = {
            "_type": "playlist",
            "description": "Carousel",
            "entries": [
                _video_entry(),
                _image_entry("https://cdn/a.jpg"),
                _image_entry("https://cdn/b.jpg"),
            ],
        }
        downloaded = {
            "entries": [{"requested_downloads": [{"filepath": file_path}]}]
        }

        extract, download, mkdtemp = self._patches(info, downloaded)
        with extract, download as download_mock, mkdtemp:
            artifacts = await self.resolver.resolve(POST_URL)

        self.assertEqual(download_mock.call_args.args[2], 0)
        self.assertEqual(len(artifacts), 2)
        video, gallery = artifacts
        self.assertIsInstance(video, VideoArtifact)
        self.assertEqual(video.caption, "Carousel")
        self.assertIsInstance(gallery, GalleryArtifact)
        self.assertEqual(
            [item.url for item in gallery.items],
            ["https://cdn/a.jpg", "https://cdn/b.jpg"],
        )

    async def test_rejects_long_video_without_download(self) -> None:
        info = dict(_video_entry(duration=3600), description="Long talk")

        with patch.object(
            InstagramResolver, "_extract_info", return_value=info
        ), patch.object(InstagramResolver, "_download") as download_mock:
            artifacts = await self.resolver.resolve(POST_URL)

        download_mock.assert_not_called()
        self.assertEqual(len(artifacts), 1)
        artifact = artifacts[0]
        self.assertIsInstance(artifact, TextArtifact)
        self.assertEqual(artifact.post_url, POST_URL)
        self.assertIn("60:00", artifact.body)

    async def test_rejects_oversized_file_and_removes_it(self) -> None:
        file_path = self._write_file(2048)
        info = dict(_video_entry(), description="Heavy")
        downloaded = {"requested_downloads": [{"filepath": file_path}]}

        extract, download, mkdtemp = self._patches(info, downloaded)
        with extract, download, mkdtemp:
            artifacts = await self.resolver.resolve(POST_URL)

        self.assertFalse(os.path.exists(file_path))
        self.assertFalse(os.path.isdir(self.download_dir))
        self.assertEqual(len(artifacts), 1)
        self.assertIsInstance(artifacts[0], TextArtifact)

    async def test_removes_download_dir_when_no_file_produced(self) -> None:
        info = _video_entry()

        extract, download, mkdtemp = self._patches(info, {})
        with extract, download, mkdtemp:
            artifacts = await self.resolver.resolve(POST_URL)

        self.assertEqual(artifacts, [])
        self.assertFalse(os.path.isdir(self.download_dir))

    async def test_removes_download_dir_when_download_raises(self) -> None:
        info = _video_entry()
        self._write_file(8)

        with patch.object(
            InstagramResolver, "_extract_info", return_value=info
        ), patch.object(
            InstagramResolver, "_download", side_effect=RuntimeError("boom")
        ), patch(
            "providers.instagram.resolver.tempfile.mkdtemp",
            return_value=self.download_dir,
        ):
            with self.assertRaises(RuntimeError):
                await self.resolver.resolve(POST_URL)

        self.assertFalse(os.path.isdir(self.download_dir))

    async def test_ignores_non_media_url(self) -> None:
        artifacts = await self.resolver.resolve(
            "https://www.instagram.com/someuser/"
        )
        self.assertEqual(artifacts, [])


if __name__ == "__main__":
    unittest.main()
