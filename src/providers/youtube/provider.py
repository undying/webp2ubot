import logging

from core.artifacts import Artifact
from providers.youtube.cookies import materialize_cookies
from providers.youtube.detector import is_youtube_url
from providers.youtube.resolver import YoutubeResolver
from settings import (
    get_youtube_cookie,
    get_youtube_cookies_file,
    get_youtube_max_duration_sec,
    get_youtube_max_filesize_bytes,
    get_youtube_remote_components,
)

logger = logging.getLogger(__name__)


class YoutubeProvider:
    name = "youtube"

    def __init__(self, resolver: YoutubeResolver) -> None:
        self.resolver = resolver

    def matches(self, url: str) -> bool:
        return is_youtube_url(url)

    async def resolve(self, url: str) -> list[Artifact]:
        return await self.resolver.resolve(url)


def build_youtube_provider() -> YoutubeProvider | None:
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        logger.warning("yt-dlp is not installed, YouTube provider disabled")
        return None

    cookies_file = materialize_cookies(
        get_youtube_cookie(),
        get_youtube_cookies_file(),
    )
    if not cookies_file:
        logger.warning(
            "No YouTube cookies configured, set YOUTUBE_COOKIE; "
            "most videos will fail with a bot check"
        )

    resolver = YoutubeResolver(
        max_duration_sec=get_youtube_max_duration_sec(),
        max_filesize_bytes=get_youtube_max_filesize_bytes(),
        cookies_file=cookies_file,
        remote_components=get_youtube_remote_components(),
    )
    return YoutubeProvider(resolver)
