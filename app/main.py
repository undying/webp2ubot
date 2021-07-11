
import os
import io
import requests
import re
import tempfile
import telegram
import telegram.ext

from PIL import Image

WEBP_URL_REGEXP = re.compile(r'(https?:\/\/[^ ]+\.webp)')


def webp_download(url: str) -> bytes:
    return True


def webp_find_url(body: str) -> list[str]:
    return re.findall(WEBP_URL_REGEXP, body)


def webp_bot(
        update: telegram.Update,
        context: telegram.ext.CallbackContext) -> None:

    webp = []
    for u in webp_find_url(update.message.text):
        r = requests.get(u)
        webp.append(r.content)

    for i in webp:
        t = tempfile.SpooledTemporaryFile(max_size=10485760, mode='w+b')

        img = Image.open(io.BytesIO(i))
        img.convert('RGB')
        img.save(t, 'JPEG')

        t.seek(0)
        f = io.BytesIO(t.read())

        update.message.reply_photo(f)


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
# reply images in album
