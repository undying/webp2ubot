import os
import re
import tempfile
import asyncio
from enum import Enum, auto
from typing import Union, Callable

import PIL.Image
import ffmpeg
import aiohttp
from telegram import Update
from telegram.ext import Application, MessageHandler, filters


URL_REGEXP = re.compile(r'(https?://\S+)')
REQUEST_TIMEOUT = 8


class MediaType(Enum):
    IMAGE = auto()
    VIDEO = auto()


class Media():
    CONVERT_MAP = {
        'image/webp': {
            'ext': '.webp',
            'type': MediaType.IMAGE
        },
        'video/webm': {
            'ext': '.webm',
            'type': MediaType.VIDEO,
            'convert': {
                'format': 'mp4', 'vcodec': 'libx264'
            }
        },
    }

    def __init__(self, url: str) -> None:
        self._convertor: Union[None, Callable[[], bool]] = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:60.0) Gecko/20100101 Firefox/60.0',
            'Referer': url
        }

        self.url = url
        self.input = tempfile.NamedTemporaryFile(mode='w+b')
        self.output = tempfile.NamedTemporaryFile(mode='w+b')

        self.media_type: Union[MediaType, None] = None
        self.type_name = None

    def __del__(self):
        self.input.close()
        self.output.close()

    def _set_type(self, type_name: str) -> None:
        self.type_name = type_name
        self.media_type = self.CONVERT_MAP[type_name]['type']

    async def _get_type(self) -> None:
        for k, v in self.CONVERT_MAP.items():
            if str(v['ext']) not in self.url:
                continue
            return self._set_type(k)

        async with aiohttp.ClientSession() as session:
            async with session.head(self.url, timeout=REQUEST_TIMEOUT, headers=self.headers) as r:
                r.raise_for_status()
                content_type = r.headers['content-type']
                if content_type not in self.CONVERT_MAP:
                    return
                self._set_type(content_type)

    @property
    def is_supported(self) -> bool:
        return self.type_name is not None

    async def download(self) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.get(self.url, timeout=REQUEST_TIMEOUT, headers=self.headers) as r:
                r.raise_for_status()
                async for chunk in r.content.iter_chunked(4096):
                    self.input.write(chunk)

        self.input.flush()
        self.input.seek(0)

    def convert(self) -> bool:
        is_supported = self.CONVERT_MAP.get(self.type_name, False)
        if not is_supported:
            return False

        match self.media_type:
            case MediaType.IMAGE:
                return self.convert_image()
            case MediaType.VIDEO:
                return self.convert_video()
            case _:
                return False

    def convert_video(self) -> bool:
        (
            ffmpeg
            .input(self.input.name)
            .output(self.output.name, **self.CONVERT_MAP[self.type_name]['convert'])
            .overwrite_output()
            .run()
        )
        self.output.seek(0)
        return True

    def convert_image(self) -> bool:
        img = PIL.Image.open(self.input)
        img.convert('RGB')
        img.save(self.output, 'JPEG')
        self.output.seek(0)
        return True


def url_find(message: Update.message) -> list[str]:
    urls = []
    for e in message.parse_entities(['url', 'text_link']):
        if e.url is not None:
            urls.append(str(e['url']))

    if message.text is not None:
        for u in re.findall(URL_REGEXP, message.text):
            urls.append(u)

    return urls


async def webp_bot(update: Update, context) -> None:
    urls = url_find(update.message)
    if len(urls) < 1:
        return

    media = map(Media, urls)
    for m in media:
        await m._get_type()
        if not m.is_supported:
            continue

        await m.download()
        m.convert()

        match m.media_type:
            case MediaType.IMAGE:
                await update.message.reply_photo(m.output)
            case MediaType.VIDEO:
                await update.message.reply_video(m.output)
            case _:
                continue


async def main() -> None:
    token = os.getenv('WEBP2U_TOKEN')
    application = Application.builder().token(token).build()
    
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            webp_bot))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    stop_signal = asyncio.Future()
    await stop_signal


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


# TODO
# parallel download images
# reply images in album
