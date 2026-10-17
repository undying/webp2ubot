import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.transcriber import TranscribeError, Transcriber, build_transcriber
from main import chat_allowed, handle_media, media_of, split_text


class SplitTextTests(unittest.TestCase):
    def test_short_text_stays_whole(self):
        self.assertEqual(split_text("привет"), ["привет"])

    def test_long_text_is_split_not_truncated(self):
        text = "\n".join("строка %d" % i for i in range(2000))
        chunks = split_text(text)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 4096 for c in chunks))
        self.assertEqual("".join(chunks).replace("\n", ""), text.replace("\n", ""))

    def test_split_prefers_line_breaks(self):
        text = "a" * 4000 + "\n" + "b" * 500
        self.assertEqual(split_text(text)[0], "a" * 4000)

    def test_unbroken_run_is_cut_by_length(self):
        chunks = split_text("x" * 5000)
        self.assertEqual(len(chunks[0]), 4096)
        self.assertEqual(len(chunks[1]), 904)


class ChatAllowedTests(unittest.TestCase):
    def check(self, allowed, chat_id):
        message = MagicMock()
        message.chat_id = chat_id
        with patch.dict(os.environ, {"ALLOWED_CHAT_IDS": allowed}):
            return chat_allowed(message)

    def test_empty_whitelist_allows_everyone(self):
        self.assertTrue(self.check("", 1))

    def test_listed_chat_passes(self):
        self.assertTrue(self.check("1, 2", 2))

    def test_unlisted_chat_is_refused(self):
        self.assertFalse(self.check("1, 2", 3))

    def test_junk_in_the_list_does_not_open_the_door(self):
        self.assertFalse(self.check("1, что-то", 3))


class MediaOfTests(unittest.TestCase):
    def message(self, **kinds):
        message = MagicMock()
        for name in ("voice", "video_note", "audio", "video", "document"):
            setattr(message, name, kinds.get(name))
        return message

    def test_voice_is_named_as_ogg(self):
        voice = MagicMock()
        self.assertEqual(media_of(self.message(voice=voice)), (voice, "voice.ogg"))

    def test_video_note_is_named_as_mp4(self):
        note = MagicMock()
        self.assertEqual(media_of(self.message(video_note=note)), (note, "note.mp4"))

    def test_document_keeps_its_name(self):
        document = MagicMock()
        document.file_name = "podcast.m4a"
        self.assertEqual(media_of(self.message(document=document))[1], "podcast.m4a")

    def test_nameless_document_gets_a_fallback(self):
        document = MagicMock()
        document.file_name = None
        self.assertEqual(media_of(self.message(document=document))[1], "file.bin")

    def test_voice_wins_over_the_rest(self):
        voice, audio = MagicMock(), MagicMock()
        self.assertEqual(media_of(self.message(voice=voice, audio=audio))[0], voice)

    def test_message_without_media(self):
        self.assertIsNone(media_of(self.message()))


class BuildTranscriberTests(unittest.TestCase):
    def build(self, **env):
        with patch.dict(os.environ, env, clear=False):
            return build_transcriber()

    def test_disabled_without_url(self):
        self.assertIsNone(self.build(TRANSCRIBE_BASE_URL="", TRANSCRIBE_TOKEN="t"))

    def test_disabled_without_token(self):
        self.assertIsNone(self.build(TRANSCRIBE_BASE_URL="http://x", TRANSCRIBE_TOKEN=""))

    def test_built_when_both_are_set(self):
        client = self.build(TRANSCRIBE_BASE_URL="http://x/", TRANSCRIBE_TOKEN="t")
        self.assertEqual(client.base_url, "http://x")


class AwaitResultTests(unittest.IsolatedAsyncioTestCase):
    def client(self, replies):
        client = Transcriber("http://x", "t", poll_interval=0, poll_timeout=5)
        client._request = AsyncMock(side_effect=list(replies))
        return client

    async def test_polls_until_done(self):
        client = self.client([
            {"state": "running", "poll_after": 0},
            {"state": "done", "text": "привет", "lines": 1},
            {"ok": True},
        ])
        with patch("asyncio.sleep", new=AsyncMock()):
            result = await client._await_result("job")
        self.assertEqual(result.text, "привет")
        self.assertEqual(result.lines, 1)

    async def test_failure_carries_the_detail(self):
        client = self.client([{"state": "failed", "detail": "нода недоступна"}])
        with self.assertRaises(TranscribeError) as caught:
            await client._await_result("job")
        self.assertIn("нода недоступна", str(caught.exception))

    async def test_empty_transcript_is_an_error(self):
        client = self.client([{"state": "done", "text": "   "}])
        with self.assertRaises(TranscribeError):
            await client._await_result("job")

    async def test_the_job_is_dropped_after_success(self):
        client = self.client([{"state": "done", "text": "t", "lines": 1}, {"ok": True}])
        await client._await_result("job")
        self.assertEqual(client._request.await_args.args, ("DELETE", "/v1/transcribe/job"))

    async def test_a_failed_cleanup_does_not_lose_the_text(self):
        client = Transcriber("http://x", "t", poll_interval=0, poll_timeout=5)
        client._request = AsyncMock(side_effect=[
            {"state": "done", "text": "текст", "lines": 1},
            TranscribeError("сервис недоступен"),
        ])
        self.assertEqual((await client._await_result("job")).text, "текст")

    async def test_submit_without_job_id_is_an_error(self):
        client = Transcriber("http://x", "t")
        client._request = AsyncMock(return_value={})
        with self.assertRaises(TranscribeError):
            await client._submit(b"audio", "voice.ogg")


class HandleMediaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.message = AsyncMock()
        self.message.message_id = 42
        self.message.chat_id = 1
        for name in ("video_note", "audio", "video", "document"):
            setattr(self.message, name, None)
        self.message.voice = MagicMock(file_id="f", file_size=1000, duration=5)
        self.bot = AsyncMock()
        source = AsyncMock()
        source.download_as_bytearray = AsyncMock(return_value=bytearray(b"audio"))
        self.bot.get_file = AsyncMock(return_value=source)
        self.client = AsyncMock()

    async def run_handler(self):
        with patch("main.typing"), patch.dict(os.environ, {"ADMIN_CHAT_ID": "7"}):
            await handle_media(self.message, self.client, self.bot)

    async def test_transcript_is_replied(self):
        self.client.transcribe = AsyncMock(
            return_value=MagicMock(text="привет", lines=1))
        await self.run_handler()
        self.client.transcribe.assert_awaited_once_with(b"audio", "voice.ogg")
        self.assertEqual(self.message.reply_text.await_args.args[0], "привет")

    async def test_oversized_file_is_refused_before_download(self):
        self.message.voice = MagicMock(file_id="f", file_size=50 * 1024 * 1024, duration=5)
        await self.run_handler()
        self.bot.get_file.assert_not_awaited()
        self.assertIn("МБ", self.message.reply_text.await_args.args[0])

    async def test_failure_tells_the_user_once_and_the_admin(self):
        self.client.transcribe = AsyncMock(side_effect=TranscribeError("нода спит"))
        await self.run_handler()
        self.assertIn("Не смог", self.message.reply_text.await_args.args[0])
        self.assertIn("нода спит", self.bot.send_message.await_args.kwargs["text"])

    async def test_long_recording_gets_a_placeholder_that_is_removed(self):
        self.message.voice = MagicMock(file_id="f", file_size=1000, duration=600)
        placeholder = AsyncMock()
        self.message.reply_text = AsyncMock(return_value=placeholder)
        self.client.transcribe = AsyncMock(return_value=MagicMock(text="t", lines=1))
        await self.run_handler()
        placeholder.delete.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
