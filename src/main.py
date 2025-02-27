
import os
import re
import tempfile

from typing import Union, Callable

import PIL.Image
import ffmpeg
import requests
import telegram
import telegram.ext


URL_REGEXP = re.compile(r'(https?://\S+)')
REQUEST_TIMEOUT = 5

CONVERT_MAP = {
    'image/webp': {},
    'video/webm': {'format': 'mp4', 'vcodec': 'libx264'},
}


class Media():
    def __init__(self, url: str) -> None:
        self._convertor: Union[None, Callable[[], bool]] = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:60.0) Gecko/20100101 Firefox/60.0',
            'Referer': url
        }

        self.url = url
        self.input = tempfile.NamedTemporaryFile(mode='w+b')
        self.output = tempfile.NamedTemporaryFile(mode='w+b')

        self.is_image = False
        self.is_video = False

        self._get_type()

    def __del__(self):
        self.input.close()
        self.output.close()

    def _get_type(self) -> None:
        if '.webp' in self.url:
            self._convertor = self.convert_image
            self.is_image = True
            self.type = 'image/webp'
            return
        if '.webm' in self.url:
            self._convertor = self.convert_video
            self.is_video = True
            self.type = 'video/webm'
            return

        r = requests.head(self.url, timeout=REQUEST_TIMEOUT, headers=self.headers)
        r.raise_for_status()

        self.type = r.headers['content-type']
        tsplit = self.type.split('/')

        if len(tsplit) < 1:
            return

        if tsplit[0] == 'image':
            self._convertor = self.convert_image
            self.is_image = True
        elif tsplit[0] == 'video':
            self._convertor = self.convert_video
            self.is_video = True

    def download(self) -> None:
        r = requests.get(
            self.url,
            stream=True,
            timeout=REQUEST_TIMEOUT,
            headers=self.headers)

        r.raise_for_status()

        for c in r.iter_content(chunk_size=4096):
            self.input.write(c)

        self.input.flush()
        self.input.seek(0)

    def convert(self) -> bool:
        convert_to = CONVERT_MAP.get(self.type, None)
        if convert_to is None:
            return False

        if self._convertor is not None:
            return self._convertor()

        return False

    def convert_video(self) -> bool:
        print('converting video...')
        (
            ffmpeg
            .input(self.input.name)
            .output(self.output.name, **CONVERT_MAP[self.type])
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


def url_find(body: str) -> list[str]:
    return re.findall(URL_REGEXP, body)


def webp_bot(
        update: telegram.Update,
        context: telegram.ext.CallbackContext) -> None:
    urls = url_find(update.message.text)
    if len(urls) < 1:
        return

    media = map(Media, urls)
    for m in media:
        m.download()
        if not m.convert():
            continue

        if m.is_image:
            update.message.reply_photo(m.output)
        elif m.is_video:
            update.message.reply_video(m.output)


def main() -> None:
    token = os.getenv('WEBP2U_TOKEN')
    updater = telegram.ext.Updater(token)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(
            telegram.ext.MessageHandler(
                telegram.ext.Filters.text & ~telegram.ext.Filters.command,
                webp_bot))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()


# TODO
# parallel download images
# reply images in album
