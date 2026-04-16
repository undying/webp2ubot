import os
import time
from typing import Any, Protocol
from urllib.parse import urlparse, urlunparse

import aiohttp

from settings import get_reddit_user_agent


TOKEN_ENDPOINT = "https://www.reddit.com/api/v1/access_token"
API_ENDPOINT = "https://oauth.reddit.com"
PUBLIC_API_ENDPOINT = "https://www.reddit.com"


class RedditClientError(Exception):
    pass


class RedditClientLike(Protocol):
    async def fetch_post_data(self, source_url: str) -> dict[str, Any] | None:
        ...


class RedditClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        request_timeout: int = 12,
        retry_count: int = 2,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.request_timeout = request_timeout
        self.retry_count = retry_count
        self._access_token: str | None = None
        self._token_expiry_ts = 0.0

    @classmethod
    def from_env(cls) -> "RedditClient":
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = get_reddit_user_agent()
        if not client_id or not client_secret:
            raise RedditClientError(
                "Missing Reddit credentials. "
                "Required: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET"
            )
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )

    @classmethod
    def from_env_or_none(cls) -> "RedditClient | None":
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = get_reddit_user_agent()
        if not client_id or not client_secret:
            return None
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )

    async def _ensure_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expiry_ts:
            return self._access_token

        headers = {"User-Agent": self.user_agent}
        auth = aiohttp.BasicAuth(self.client_id, self.client_secret)
        data = {"grant_type": "client_credentials"}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(
                TOKEN_ENDPOINT,
                data=data,
                auth=auth,
                timeout=self.request_timeout,
            ) as response:
                response.raise_for_status()
                payload = await response.json()

        token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 3600))
        if not token:
            raise RedditClientError(
                "Reddit token response does not contain access_token"
            )

        self._access_token = token
        self._token_expiry_ts = time.time() + max(60, expires_in - 30)
        return token

    async def fetch_post_data(self, source_url: str) -> dict[str, Any] | None:
        payload: dict[str, Any] | None = None
        last_exception: Exception | None = None
        for attempt in range(self.retry_count + 1):
            token = await self._ensure_access_token()
            headers = {
                "Authorization": f"bearer {token}",
                "User-Agent": self.user_agent,
            }
            params = {"url": source_url}
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(
                        f"{API_ENDPOINT}/api/info",
                        params=params,
                        timeout=self.request_timeout,
                    ) as response:
                        if (
                            response.status == 401
                            and attempt < self.retry_count
                        ):
                            self._access_token = None
                            self._token_expiry_ts = 0.0
                            continue
                        response.raise_for_status()
                        payload = await response.json()
                        break
            except Exception as exc:
                last_exception = exc

        if payload is None:
            if last_exception:
                raise last_exception
            return None

        children = payload.get("data", {}).get("children", [])
        if not children:
            return None
        return children[0].get("data")


class PublicRedditClient:
    def __init__(
        self,
        user_agent: str,
        request_timeout: int = 12,
        retry_count: int = 2,
        cookie: str | None = None,
        referer: str | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.request_timeout = request_timeout
        self.retry_count = retry_count
        self.cookie = cookie
        self.referer = referer

    async def fetch_post_data(self, source_url: str) -> dict[str, Any] | None:
        resolved_source_url = await self._resolve_source_url(source_url)
        json_url = self._post_json_url(resolved_source_url)
        headers = self._build_headers()
        last_exception: Exception | None = None
        for _ in range(self.retry_count + 1):
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(
                        json_url,
                        params={"raw_json": "1"},
                        timeout=self.request_timeout,
                    ) as response:
                        response.raise_for_status()
                        if not self._is_json_response(response):
                            return None
                        payload = await response.json()
                        return self._extract_post_data(payload)
            except Exception as exc:
                last_exception = exc
        if last_exception:
            raise last_exception
        return None

    async def _resolve_source_url(self, source_url: str) -> str:
        if not self._requires_share_resolution(source_url):
            return source_url

        headers = self._build_headers()
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(
                source_url,
                allow_redirects=True,
                timeout=self.request_timeout,
            ) as response:
                response.raise_for_status()
                return str(response.url)

    @staticmethod
    def _is_json_response(response: aiohttp.ClientResponse) -> bool:
        content_type = response.headers.get("Content-Type", "")
        return "application/json" in content_type.lower()

    @staticmethod
    def _requires_share_resolution(source_url: str) -> bool:
        parsed = urlparse(source_url)
        path_parts = [part for part in parsed.path.split("/") if part]
        return len(path_parts) >= 2 and path_parts[-2] == "s"

    def _build_headers(self) -> dict[str, str]:
        headers = {"User-Agent": self.user_agent}
        if self.cookie:
            headers["Cookie"] = self.cookie
            headers["Referer"] = self.referer or "https://www.reddit.com/"
        return headers

    @staticmethod
    def _post_json_url(source_url: str) -> str:
        parsed = urlparse(source_url)
        path = parsed.path or "/"
        if not path.endswith(".json"):
            path = path.rstrip("/")
            if not path:
                path = "/"
            path = f"{path}.json"
        normalized = parsed._replace(
            scheme="https",
            netloc="www.reddit.com",
            path=path,
            params="",
            query="",
            fragment="",
        )
        return urlunparse(normalized)

    @staticmethod
    def _extract_post_data(payload: Any) -> dict[str, Any] | None:
        if not isinstance(payload, list) or len(payload) < 1:
            return None
        listing = payload[0]
        children = listing.get("data", {}).get("children", [])
        if not children:
            return None
        return children[0].get("data")


def build_reddit_client() -> tuple[RedditClientLike, str]:
    oauth_client = RedditClient.from_env_or_none()
    if oauth_client:
        return oauth_client, "oauth"
    cookie = os.getenv("REDDIT_PUBLIC_COOKIE")
    referer = os.getenv("REDDIT_PUBLIC_REFERER")
    user_agent = get_reddit_user_agent()
    public_client = PublicRedditClient(
        user_agent=user_agent,
        cookie=cookie,
        referer=referer,
    )
    if cookie:
        return public_client, "public_json_cookie"
    return public_client, "public_json_anonymous"
