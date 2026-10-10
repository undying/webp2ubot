import asyncio
import io
import logging
import tempfile
from enum import Enum, auto
from typing import Any

import PIL.Image
import aiohttp
import ffmpeg

from core.artifacts import (
    Artifact,
    ImageArtifact,
    VideoArtifact,
    remove_temp_file,
)

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 8
DOWNLOAD_CHUNK_BYTES = 4096
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 6.1; rv:60.0) Gecko/20100101 Firefox/60.0'
)


class MediaType(Enum):
    IMAGE = auto()
    VIDEO = auto()


CONVERT_MAP: dict[str, dict[str, Any]] = {
    'image/webp': {
        'ext': '.webp',
        'type': MediaType.IMAGE,
    },
    'video/webm': {
        'ext': '.webm',
        'type': MediaType.VIDEO,
        'convert': {'format': 'mp4', 'vcodec': 'libx264'},
    },
}


class DirectProvider:
    """Fallback for plain links to a media file: webp -> jpeg, webm -> mp4."""

    name = "direct"

    def matches(self, url: str) -> bool:
        return True

    async def resolve(self, url: str) -> list[Artifact]:
        content_type = await self._detect_content_type(url)
        if content_type is None:
            return []

        media_type = CONVERT_MAP[content_type]['type']
        payload = await self._download(url)
        output_path = await asyncio.to_thread(
            self._convert,
            payload,
            content_type,
            media_type,
        )
        match media_type:
            case MediaType.IMAGE:
                return [ImageArtifact(url=url, file_path=output_path)]
            case MediaType.VIDEO:
                return [VideoArtifact(url=url, file_path=output_path)]
            case _:
                return []

    @staticmethod
    def _headers(url: str) -> dict[str, str]:
        return {'User-Agent': USER_AGENT, 'Referer': url}

    async def _detect_content_type(self, url: str) -> str | None:
        for content_type, spec in CONVERT_MAP.items():
            if str(spec['ext']) in url:
                return content_type

        async with aiohttp.ClientSession() as session:
            async with session.head(
                url,
                timeout=REQUEST_TIMEOUT,
                headers=self._headers(url),
            ) as response:
                response.raise_for_status()
                content_type = response.headers.get('content-type', '')
        if content_type not in CONVERT_MAP:
            return None
        return content_type

    async def _download(self, url: str) -> bytes:
        parts: list[bytes] = []
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=REQUEST_TIMEOUT,
                headers=self._headers(url),
            ) as response:
                response.raise_for_status()
                async for chunk in response.content.iter_chunked(
                    DOWNLOAD_CHUNK_BYTES
                ):
                    parts.append(chunk)
        return b''.join(parts)

    @staticmethod
    def _convert(
        payload: bytes,
        content_type: str,
        media_type: MediaType,
    ) -> str:
        suffix = '.jpg' if media_type is MediaType.IMAGE else '.mp4'
        with tempfile.NamedTemporaryFile(
            mode='w+b',
            suffix=suffix,
            delete=False,
        ) as output_file:
            output_path = output_file.name

        try:
            if media_type is MediaType.IMAGE:
                image = PIL.Image.open(io.BytesIO(payload))
                image.convert('RGB').save(output_path, 'JPEG')
                return output_path

            with tempfile.NamedTemporaryFile(
                mode='w+b',
                suffix=str(CONVERT_MAP[content_type]['ext']),
            ) as input_file:
                input_file.write(payload)
                input_file.flush()
                (
                    ffmpeg
                    .input(input_file.name)
                    .output(
                        output_path,
                        **CONVERT_MAP[content_type]['convert'],
                    )
                    .overwrite_output()
                    .run()
                )
            return output_path
        except Exception:
            remove_temp_file(output_path)
            raise
