import os
import re
import asyncio
import logging
from typing import Any

from telegram import Update, Message
from telegram.ext import Application, MessageHandler, filters

from core.artifacts import cleanup_artifacts
from core.provider import Provider, build_providers
from core.sender import MediaSender


URL_REGEXP = re.compile(r'(https?://\S+)')
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
    if "Sign in to confirm" in text or "cookies" in text.lower():
        return "YouTube просит авторизацию, нужна свежая кука."
    if "Private video" in text or "members-only" in text:
        return "Видео приватное."
    if "unavailable" in text.lower():
        return "Видео недоступно."
    return "Не смог забрать медиа по этой ссылке."


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
            await message.reply_text(
                failure_reason(exc),
                reply_to_message_id=message.message_id,
                disable_web_page_preview=True,
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


async def webp_bot(update: Update, context: Any) -> None:
    if not update.message:
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
