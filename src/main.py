
import PIL.Image
import os
import re
import requests
import telegram
import telegram.ext
import tempfile

WEBP_URL_REGEXP = re.compile(r'(https?:\/\/[^ ]+\.webp)')
URL_REGEXP = re.compile(r'(https?://\S+)')


class Image():
    def __init__(self, url: str) -> None:
        self.url = url
        self.input = tempfile.SpooledTemporaryFile(
                max_size=10485760, mode='w+b')
        self.output = tempfile.SpooledTemporaryFile(
                max_size=10485760, mode='w+b')

    def __del__(self):
        self.input.close()
        self.output.close()

    def download(self) -> None:
        r = requests.get(self.url, stream=True)
        r.raise_for_status()

        for c in r.iter_content(chunk_size=4096):
            self.input.write(c)

        self.input.seek(0)

    def to_jpeg(self) -> None:
        img = PIL.Image.open(self.input)
        img.convert('RGB')
        img.save(self.output, 'JPEG')

        self.output.seek(0)


def webp_url_find(url: str) -> bool:
    if '.webp' in url:
        return True

    r = requests.head(url)
    r.raise_for_status()

    if r.headers['content-type'] == 'image/webp':
        return True

    return False


def url_find(body: str) -> list[str]:
    return re.findall(URL_REGEXP, body)


def webp_bot(
        update: telegram.Update,
        context: telegram.ext.CallbackContext) -> None:
    webp_urls = filter(webp_url_find, url_find(update.message.text))
    images = map(Image, webp_urls)

    for i in images:
        i.download()
        i.to_jpeg()
        update.message.reply_photo(i.output)


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
