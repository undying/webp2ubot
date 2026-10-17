import asyncio
import logging
from dataclasses import dataclass

import aiohttp

from settings import (
    get_transcribe_base_url,
    get_transcribe_poll_interval_sec,
    get_transcribe_poll_timeout_sec,
    get_transcribe_request_timeout_sec,
    get_transcribe_token,
)

logger = logging.getLogger(__name__)


class TranscribeError(Exception):
    pass


@dataclass
class Transcript:
    text: str
    lines: int


class Transcriber:
    def __init__(
        self,
        base_url: str,
        token: str,
        poll_interval: int | None = None,
        poll_timeout: int | None = None,
        request_timeout: int | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.poll_interval = (
            poll_interval
            if poll_interval is not None
            else get_transcribe_poll_interval_sec()
        )
        self.poll_timeout = (
            poll_timeout
            if poll_timeout is not None
            else get_transcribe_poll_timeout_sec()
        )
        self.request_timeout = (
            request_timeout
            if request_timeout is not None
            else get_transcribe_request_timeout_sec()
        )

    async def transcribe(self, payload: bytes, file_name: str) -> Transcript:
        job_id = await self._submit(payload, file_name)
        return await self._await_result(job_id)

    async def _submit(self, payload: bytes, file_name: str) -> str:
        headers = {
            "Content-Type": "application/octet-stream",
            "X-Filename": file_name,
        }
        body = await self._request(
            "POST",
            "/v1/transcribe",
            data=payload,
            headers=headers,
        )
        job_id = body.get("job_id")
        if not job_id:
            raise TranscribeError("ответ без job_id")
        return str(job_id)

    async def _await_result(self, job_id: str) -> Transcript:
        deadline = asyncio.get_running_loop().time() + self.poll_timeout
        while True:
            body = await self._request("GET", f"/v1/transcribe/{job_id}")
            state = body.get("state")
            if state == "done":
                text = str(body.get("text") or "").strip()
                if not text:
                    raise TranscribeError("пустой транскрипт")
                await self._forget(job_id)
                return Transcript(text=text, lines=int(body.get("lines") or 0))
            if state == "failed":
                raise TranscribeError(str(body.get("detail") or "расшифровка не удалась"))
            if asyncio.get_running_loop().time() > deadline:
                raise TranscribeError("расшифровка не уложилась в отведённое время")
            await asyncio.sleep(max(1, int(body.get("poll_after") or self.poll_interval)))

    async def _forget(self, job_id: str) -> None:
        try:
            await self._request("DELETE", f"/v1/transcribe/{job_id}")
        except Exception as exc:
            logger.warning("Failed to drop transcription job %s: %s", job_id, exc)

    async def _request(
        self,
        method: str,
        path: str,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict:
        request_headers = {"Authorization": f"Bearer {self.token}"}
        request_headers.update(headers or {})
        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method,
                    self.base_url + path,
                    data=data,
                    headers=request_headers,
                ) as response:
                    body = await self._read_json(response)
                    if response.status >= 400:
                        raise TranscribeError(self._error_text(response.status, body))
                    return body
        except aiohttp.ClientError as exc:
            raise TranscribeError(f"сервис расшифровки недоступен: {exc}") from exc
        except asyncio.TimeoutError as exc:
            raise TranscribeError("сервис расшифровки не ответил вовремя") from exc

    @staticmethod
    async def _read_json(response: aiohttp.ClientResponse) -> dict:
        try:
            body = await response.json(content_type=None)
        except Exception:
            return {}
        return body if isinstance(body, dict) else {}

    @staticmethod
    def _error_text(status: int, body: dict) -> str:
        detail = body.get("error") or body.get("detail")
        return f"{detail}" if detail else f"сервис расшифровки ответил {status}"


def build_transcriber() -> Transcriber | None:
    base_url = get_transcribe_base_url()
    token = get_transcribe_token()
    if not base_url or not token:
        logger.info("Transcription disabled: TRANSCRIBE_BASE_URL/TRANSCRIBE_TOKEN unset")
        return None
    return Transcriber(base_url=base_url, token=token)
