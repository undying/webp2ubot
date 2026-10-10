import unittest
import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.artifacts import TextArtifact
from main import failure_reason, handle_url


class _Provider:
    def __init__(self, name, matches, result=None, error=None):
        self.name = name
        self._matches = matches
        self._result = result or []
        self._error = error

    def matches(self, url):
        return self._matches

    async def resolve(self, url):
        if self._error:
            raise self._error
        return self._result


class HandleUrlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.message = AsyncMock()
        self.message.message_id = 42
        self.sender = AsyncMock()

    async def test_replies_when_provider_raises(self) -> None:
        provider = _Provider(
            "youtube",
            True,
            error=RuntimeError("Sign in to confirm you're not a bot"),
        )
        await handle_url(self.message, [provider], self.sender, "u")

        self.message.reply_text.assert_awaited_once()
        args, kwargs = self.message.reply_text.await_args
        self.assertIn("кука", args[0])
        self.assertEqual(kwargs["reply_to_message_id"], 42)
        self.sender.send.assert_not_awaited()

    async def test_stays_silent_when_nothing_resolved(self) -> None:
        provider = _Provider("direct", True, result=[])
        await handle_url(self.message, [provider], self.sender, "u")

        self.message.reply_text.assert_not_awaited()
        self.sender.send.assert_not_awaited()

    async def test_first_matching_provider_wins(self) -> None:
        artifact = TextArtifact(title="t", body="b", post_url="u")
        first = _Provider("reddit", False)
        second = _Provider("youtube", True, result=[artifact])
        third = _Provider("direct", True, result=[])

        await handle_url(self.message, [first, second, third], self.sender, "u")

        self.sender.send.assert_awaited_once()
        self.message.reply_text.assert_not_awaited()

    def test_failure_reason_mapping(self) -> None:
        self.assertIn(
            "кука",
            failure_reason(RuntimeError("Sign in to confirm you're not a bot")),
        )
        self.assertIn("приватное", failure_reason(RuntimeError("Private video")))
        self.assertIn(
            "недоступно",
            failure_reason(RuntimeError("This video is unavailable")),
        )
        self.assertIn("Не смог", failure_reason(RuntimeError("timeout")))


if __name__ == "__main__":
    unittest.main()
