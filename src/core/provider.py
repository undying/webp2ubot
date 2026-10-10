import logging
from typing import Protocol, runtime_checkable

from core.artifacts import Artifact

logger = logging.getLogger(__name__)


@runtime_checkable
class Provider(Protocol):
    name: str

    def matches(self, url: str) -> bool:
        ...

    async def resolve(self, url: str) -> list[Artifact]:
        ...


def build_providers() -> list[Provider]:
    from providers.direct.provider import DirectProvider
    from providers.reddit.provider import build_reddit_provider
    from providers.youtube.provider import build_youtube_provider

    providers: list[Provider] = []
    for factory in (build_reddit_provider, build_youtube_provider):
        provider = factory()
        if provider is None:
            continue
        providers.append(provider)
    providers.append(DirectProvider())

    logger.info(
        "Enabled providers: %s",
        ", ".join(provider.name for provider in providers),
    )
    return providers
