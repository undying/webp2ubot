import os
import re
import asyncio
import contextlib
import logging
from typing import Any, AsyncIterator

from telegram import Update, Message
from telegram.constants import ChatAction
from telegram.ext import Application, MessageHandler, filters

from core.artifacts import cleanup_artifacts
from core.provider import Provider, build_providers
from core.sender import MAX_TEXT_REPLY_LENGTH, MediaSender
from core.transcriber import TranscribeError, Transcriber, build_transcriber
from settings import (
    get_admin_chat_id,
    get_allowed_chat_ids,
    get_transcribe_max_filesize_bytes,
)


URL_REGEXP = re.compile(r'(https?://\S+)')
TYPING_REFRESH_SEC = 4
PLACEHOLDER_DURATION_SEC = 120
logger = logging.getLogger(__name__)


def url_find(message: Message) -> list[str]:
    urls: list[str] = []
    seen_urls: set[str] = set()
    entities = message.parse_entities(['url', 'text_link'])
    for entity, value in entities.items():
        entity_url = getattr(entity, "url", None)
        candidate = str(entity_url) if entity_url else str(value)
        if candidate and candidate not in seen_urls:
            seen_urls.add(candidate)
            urls.append(candidate)

    if message.text is not None:
        for u in re.findall(URL_REGEXP, message.text):
            if u not in seen_urls:
                seen_urls.add(u)
                urls.append(u)

    return urls


def failure_reason(exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()
    if (
        "Sign in to confirm" in text
        or "login required" in lowered
        or "cookies" in lowered
    ):
        return "Сайт просит авторизацию, нужна свежая кука."
    if "rate-limit reached" in lowered or "please wait a few minutes" in lowered:
        return "Сайт просит подождать, слишком много запросов."
    if "Private video" in text or "members-only" in text:
        return "Видео приватное."
    if "unavailable" in text.lower():
        return "Видео недоступно."
    return "Не смог забрать медиа по этой ссылке."


def chat_allowed(message: Message) -> bool:
    allowed = get_allowed_chat_ids()
    if not allowed:
        return True
    return message.chat_id in allowed


async def notify_admin(bot: Any, text: str) -> None:
    chat_id = get_admin_chat_id()
    if not chat_id:
        return
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            disable_web_page_preview=True,
        )
    except Exception as exc:
        logger.warning("Failed to notify admin: %s", exc)


@contextlib.asynccontextmanager
async def typing(bot: Any, chat_id: int) -> AsyncIterator[None]:
    async def loop() -> None:
        while True:
            try:
                await bot.send_chat_action(chat_id, ChatAction.TYPING)
            except Exception as exc:
                logger.debug("Chat action failed: %s", exc)
            await asyncio.sleep(TYPING_REFRESH_SEC)

    task = asyncio.create_task(loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def split_text(text: str) -> list[str]:
    chunks: list[str] = []
    rest = text
    while rest:
        if len(rest) <= MAX_TEXT_REPLY_LENGTH:
            chunks.append(rest)
            break
        cut = rest.rfind("\n", 0, MAX_TEXT_REPLY_LENGTH)
        if cut <= 0:
            cut = rest.rfind(" ", 0, MAX_TEXT_REPLY_LENGTH)
        if cut <= 0:
            cut = MAX_TEXT_REPLY_LENGTH
        chunks.append(rest[:cut])
        rest = rest[cut:].lstrip()
    return chunks


def media_of(message: Message) -> tuple[Any, str] | None:
    voice = message.voice
    if voice is not None:
        return voice, "voice.ogg"
    note = message.video_note
    if note is not None:
        return note, "note.mp4"
    audio = message.audio
    if audio is not None:
        return audio, audio.file_name or "audio.mp3"
    video = message.video
    if video is not None:
        return video, video.file_name or "video.mp4"
    document = message.document
    if document is not None:
        return document, document.file_name or "file.bin"
    return None


async def handle_media(
    message: Message,
    transcriber: Transcriber,
    bot: Any,
) -> None:
    found = media_of(message)
    if found is None:
        return
    media, file_name = found

    max_bytes = get_transcribe_max_filesize_bytes()
    size = getattr(media, "file_size", None)
    if size and size > max_bytes:
        await message.reply_text(
            f"Файл больше {max_bytes // (1024 * 1024)} МБ, не смогу его забрать.",
            reply_to_message_id=message.message_id,
        )
        return

    duration = getattr(media, "duration", None) or 0
    placeholder = None
    async with typing(bot, message.chat_id):
        if duration >= PLACEHOLDER_DURATION_SEC:
            placeholder = await message.reply_text(
                f"Расшифровываю, это примерно {max(1, duration // 60)} мин записи.",
                reply_to_message_id=message.message_id,
            )
        try:
            source = await bot.get_file(media.file_id)
            payload = bytes(await source.download_as_bytearray())
            transcript = await transcriber.transcribe(payload, file_name)
        except TranscribeError as exc:
            logger.warning("Transcription failed for %s: %s", file_name, exc)
            await notify_admin(bot, f"Расшифровка не удалась: {exc}")
            await message.reply_text(
                "Не смог расшифровать.",
                reply_to_message_id=message.message_id,
            )
            return
        finally:
            if placeholder is not None:
                with contextlib.suppress(Exception):
                    await placeholder.delete()

    for chunk in split_text(transcript.text):
        await message.reply_text(
            chunk,
            reply_to_message_id=message.message_id,
            disable_web_page_preview=True,
        )


async def handle_url(
    message: Message,
    providers: list[Provider],
    sender: MediaSender,
    url: str,
) -> None:
    for provider in providers:
        if not provider.matches(url):
            continue
        try:
            artifacts = await provider.resolve(url)
        except Exception as exc:
            logger.exception(
                "Provider %s failed for url=%s",
                provider.name,
                url,
                exc_info=exc,
            )
            await notify_admin(
                message.get_bot(),
                f"{failure_reason(exc)}\n{provider.name}: {url}",
            )
            return
        if not artifacts:
            logger.info(
                "Provider %s resolved nothing for url=%s",
                provider.name,
                url,
            )
            return
        try:
            await sender.send(message, artifacts)
        finally:
            cleanup_artifacts(artifacts)
        return


async def media_bot(update: Update, context: Any) -> None:
    if not update.message or not chat_allowed(update.message):
        return
    transcriber: Transcriber | None = context.application.bot_data["transcriber"]
    if transcriber is None:
        return
    try:
        await handle_media(update.message, transcriber, context.bot)
    except Exception as exc:
        logger.exception("Failed to transcribe message", exc_info=exc)


async def webp_bot(update: Update, context: Any) -> None:
    if not update.message or not chat_allowed(update.message):
        return
    urls = url_find(update.message)
    if len(urls) < 1:
        return

    providers: list[Provider] = context.application.bot_data["providers"]
    sender: MediaSender = context.application.bot_data["sender"]

    for url in urls:
        try:
            await handle_url(update.message, providers, sender, url)
        except Exception as exc:
            logger.exception("Failed to process URL: %s", url, exc_info=exc)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.getenv('WEBP2U_TOKEN')
    application = Application.builder().token(token).build()
    application.bot_data["providers"] = build_providers()
    application.bot_data["sender"] = MediaSender()
    application.bot_data["transcriber"] = build_transcriber()

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            webp_bot))
    application.add_handler(
        MessageHandler(
            filters.VOICE
            | filters.VIDEO_NOTE
            | filters.AUDIO
            | filters.VIDEO
            | filters.Document.AUDIO
            | filters.Document.VIDEO,
            media_bot))

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
