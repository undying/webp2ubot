import logging

from core.artifacts import Artifact
from providers.reddit.client import build_reddit_client
from providers.reddit.detector import is_reddit_url
from providers.reddit.resolver import RedditResolver

logger = logging.getLogger(__name__)


class RedditProvider:
    name = "reddit"

    def __init__(self, resolver: RedditResolver) -> None:
        self.resolver = resolver

    def matches(self, url: str) -> bool:
        return is_reddit_url(url)

    async def resolve(self, url: str) -> list[Artifact]:
        return await self.resolver.resolve(url)


def build_reddit_provider() -> RedditProvider:
    client, mode = build_reddit_client()
    logger.info("Reddit provider enabled with mode=%s", mode)
    return RedditProvider(RedditResolver(client))
