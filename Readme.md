
# Telegram Bot: webp2u

## About

Your friend likes to send you memes in webp, but it pisses you off to open links in the browser?
This bot responds to messages with a webp message with a jpeg, so that you no longer have to leave the telegram to watch a funny meme.

## Installation

Just add the [@webp2ubot](http://t.me/webp2u_dev_bot) bot to your chat and enjoy the good old jpeg pictures.

Or you can run this bot on your server if you want to keep the memes closer to the body.

## TODO

- Add support for sending not only webp images from the bot. It is convenient when you want to have all the pictures in the media section.
- Add support converting webm to mp4
- Drop the YouTube cookie in favour of a PO token provider (`bgutil-ytdlp-pot-provider`, runs as a sidecar). Browser cookies get revoked by Google within minutes once they are used from another IP, so every revocation currently needs a human to paste a fresh `YOUTUBE_COOKIE`. Worth doing when that babysitting gets annoying, or when YouTube starts rejecting cookies taken from a private window too.
