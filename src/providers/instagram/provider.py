import logging

from core.artifacts import Artifact
from providers.instagram.cookies import materialize_cookies
from providers.instagram.detector import is_instagram_url
from providers.instagram.resolver import InstagramResolver
from settings import (
    get_instagram_cookie,
    get_instagram_cookies_file,
    get_instagram_max_duration_sec,
    get_instagram_max_filesize_bytes,
)

logger = logging.getLogger(__name__)


class InstagramProvider:
    name = "instagram"

    def __init__(self, resolver: InstagramResolver) -> None:
        self.resolver = resolver

    def matches(self, url: str) -> bool:
        return is_instagram_url(url)

    async def resolve(self, url: str) -> list[Artifact]:
        return await self.resolver.resolve(url)


def build_instagram_provider() -> InstagramProvider | None:
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        logger.warning("yt-dlp is not installed, Instagram provider disabled")
        return None

    cookies_file = materialize_cookies(
        get_instagram_cookie(),
        get_instagram_cookies_file(),
    )
    if not cookies_file:
        logger.warning(
            "No Instagram cookies configured, set INSTAGRAM_COOKIE; "
            "most posts will fail with a login check"
        )

    resolver = InstagramResolver(
        max_duration_sec=get_instagram_max_duration_sec(),
        max_filesize_bytes=get_instagram_max_filesize_bytes(),
        cookies_file=cookies_file,
    )
    return InstagramProvider(resolver)
