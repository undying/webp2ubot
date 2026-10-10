from html import unescape
import logging
from typing import Any

from core.artifacts import (
    GalleryArtifact,
    ImageArtifact,
    TextArtifact,
    VideoArtifact,
)
from providers.reddit.client import RedditClientLike
from providers.reddit.detector import normalize_reddit_url

logger = logging.getLogger(__name__)


class RedditResolver:
    def __init__(self, client: RedditClientLike) -> None:
        self.client = client

    async def resolve(
        self,
        url: str,
    ) -> list[ImageArtifact | GalleryArtifact | TextArtifact | VideoArtifact]:
        normalized_url = normalize_reddit_url(url)
        post_data = await self.client.fetch_post_data(normalized_url)
        if not post_data:
            logger.warning(
                "No Reddit post data resolved for url=%s",
                normalized_url,
            )
            return []
        artifacts = self._to_artifacts(post_data)
        if not artifacts:
            logger.warning(
                "No supported Reddit artifacts resolved for url=%s",
                normalized_url,
            )
        return artifacts

    def _to_artifacts(
        self,
        post_data: dict[str, Any],
    ) -> list[ImageArtifact | GalleryArtifact | TextArtifact | VideoArtifact]:
        title = str(post_data.get("title", "")).strip()
        caption = title or None
        artifacts: list[
            ImageArtifact | GalleryArtifact | TextArtifact | VideoArtifact
        ] = []

        if bool(post_data.get("is_gallery")):
            gallery_urls = self._extract_gallery_urls(post_data)
            images = [ImageArtifact(url=item_url) for item_url in gallery_urls]
            if images:
                artifacts.append(
                    GalleryArtifact(items=images, caption=caption)
                )
        else:
            video_url, dash_url = self._extract_video_data(post_data)
            if video_url:
                artifacts.append(
                    VideoArtifact(
                        url=video_url,
                        caption=caption,
                        dash_url=dash_url,
                    )
                )
            else:
                image_url = self._extract_image_url(post_data)
                if image_url:
                    artifacts.append(
                        ImageArtifact(url=image_url, caption=caption)
                    )

        text_artifact = self._extract_text_artifact(post_data, title=title)
        if text_artifact:
            artifacts.append(text_artifact)

        return artifacts

    @staticmethod
    def _extract_gallery_urls(post_data: dict[str, Any]) -> list[str]:
        metadata = RedditResolver._as_dict(post_data.get("media_metadata"))

        gallery_data = RedditResolver._as_dict(post_data.get("gallery_data"))
        media_items = gallery_data.get("items", [])
        urls: list[str] = []
        for item in media_items:
            if not isinstance(item, dict):
                continue
            media_id = item.get("media_id")
            media_meta = RedditResolver._as_dict(metadata.get(media_id))
            image_data = RedditResolver._as_dict(media_meta.get("s"))
            source_url = image_data.get("u")
            if source_url:
                urls.append(unescape(str(source_url)))
        return urls

    @staticmethod
    def _extract_video_data(
        post_data: dict[str, Any],
    ) -> tuple[str | None, str | None]:
        media = RedditResolver._as_dict(post_data.get("media"))
        reddit_video = RedditResolver._as_dict(media.get("reddit_video"))
        dash_url = reddit_video.get("dash_url")
        normalized_dash_url = (
            unescape(str(dash_url))
            if isinstance(dash_url, str) and dash_url
            else None
        )
        fallback_url = reddit_video.get("fallback_url")
        if fallback_url:
            return unescape(str(fallback_url)), normalized_dash_url

        preview = RedditResolver._as_dict(post_data.get("preview"))
        reddit_video_preview = RedditResolver._as_dict(
            preview.get("reddit_video_preview")
        )
        preview_url = reddit_video_preview.get("fallback_url")
        if preview_url:
            return unescape(str(preview_url)), normalized_dash_url

        direct_url = str(post_data.get("url_overridden_by_dest", "")).strip()
        if direct_url.lower().endswith((".gif", ".gifv", ".mp4")):
            return direct_url, normalized_dash_url
        return None, normalized_dash_url

    @staticmethod
    def _extract_image_url(post_data: dict[str, Any]) -> str | None:
        direct_url = str(post_data.get("url_overridden_by_dest", "")).strip()
        if direct_url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return direct_url

        preview = RedditResolver._as_dict(post_data.get("preview"))
        images = preview.get("images", [])
        if images:
            if not isinstance(images[0], dict):
                return None
            source = RedditResolver._as_dict(images[0].get("source"))
            source_url = source.get("url")
            if source_url:
                return unescape(str(source_url))
        return None

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {}

    @staticmethod
    def _extract_text_artifact(
        post_data: dict[str, Any],
        title: str,
    ) -> TextArtifact | None:
        body = str(post_data.get("selftext", "")).strip()
        if not body:
            return None
        permalink = str(post_data.get("permalink", "")).strip()
        post_url = f"https://www.reddit.com{permalink}" if permalink else ""
        return TextArtifact(title=title, body=body, post_url=post_url)
