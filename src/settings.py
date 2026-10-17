import os


REDDIT_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) "
    "Gecko/20100101 Firefox/149.0"
)
YOUTUBE_DEFAULT_MAX_DURATION_SEC = 600
YOUTUBE_DEFAULT_MAX_FILESIZE_MB = 48
YOUTUBE_DEFAULT_COOKIES_FILE = "secrets/youtube_cookies.txt"
INSTAGRAM_DEFAULT_MAX_DURATION_SEC = 600
INSTAGRAM_DEFAULT_MAX_FILESIZE_MB = 48
INSTAGRAM_DEFAULT_COOKIES_FILE = "secrets/instagram_cookies.txt"
TRANSCRIBE_DEFAULT_MAX_FILESIZE_MB = 20
TRANSCRIBE_DEFAULT_POLL_INTERVAL_SEC = 2
TRANSCRIBE_DEFAULT_POLL_TIMEOUT_SEC = 1800
TRANSCRIBE_DEFAULT_REQUEST_TIMEOUT_SEC = 120


def get_reddit_user_agent() -> str:
    return os.getenv("REDDIT_USER_AGENT", REDDIT_DEFAULT_USER_AGENT)


def get_youtube_max_duration_sec() -> int:
    return _get_int(
        "YOUTUBE_MAX_DURATION_SEC",
        YOUTUBE_DEFAULT_MAX_DURATION_SEC,
    )


def get_youtube_max_filesize_bytes() -> int:
    max_mb = _get_int(
        "YOUTUBE_MAX_FILESIZE_MB",
        YOUTUBE_DEFAULT_MAX_FILESIZE_MB,
    )
    return max_mb * 1024 * 1024


def get_youtube_remote_components() -> list[str]:
    raw_value = os.getenv("YOUTUBE_REMOTE_COMPONENTS", "").strip()
    if not raw_value:
        return []
    return [part.strip() for part in raw_value.split(",") if part.strip()]


def get_youtube_cookie() -> str | None:
    """Raw Cookie header copied from the browser."""

    return os.getenv("YOUTUBE_COOKIE", "").strip() or None


def get_youtube_cookies_file() -> str:
    """Netscape file yt-dlp reads and rotates; generated from YOUTUBE_COOKIE."""

    return os.getenv(
        "YOUTUBE_COOKIES_FILE",
        YOUTUBE_DEFAULT_COOKIES_FILE,
    )


def get_instagram_max_duration_sec() -> int:
    return _get_int(
        "INSTAGRAM_MAX_DURATION_SEC",
        INSTAGRAM_DEFAULT_MAX_DURATION_SEC,
    )


def get_instagram_max_filesize_bytes() -> int:
    max_mb = _get_int(
        "INSTAGRAM_MAX_FILESIZE_MB",
        INSTAGRAM_DEFAULT_MAX_FILESIZE_MB,
    )
    return max_mb * 1024 * 1024


def get_instagram_cookie() -> str | None:
    """Raw Cookie header copied from the browser."""

    return os.getenv("INSTAGRAM_COOKIE", "").strip() or None


def get_instagram_cookies_file() -> str:
    """Netscape file yt-dlp reads; generated from INSTAGRAM_COOKIE."""

    return os.getenv(
        "INSTAGRAM_COOKIES_FILE",
        INSTAGRAM_DEFAULT_COOKIES_FILE,
    )


def get_transcribe_base_url() -> str | None:
    """Base URL of the meetd transcription API; empty disables the feature."""

    return os.getenv("TRANSCRIBE_BASE_URL", "").strip().rstrip("/") or None


def get_transcribe_token() -> str | None:
    return os.getenv("TRANSCRIBE_TOKEN", "").strip() or None


def get_transcribe_max_filesize_bytes() -> int:
    max_mb = _get_int(
        "TRANSCRIBE_MAX_FILESIZE_MB",
        TRANSCRIBE_DEFAULT_MAX_FILESIZE_MB,
    )
    return max_mb * 1024 * 1024


def get_transcribe_poll_interval_sec() -> int:
    return _get_int(
        "TRANSCRIBE_POLL_INTERVAL_SEC",
        TRANSCRIBE_DEFAULT_POLL_INTERVAL_SEC,
    )


def get_transcribe_poll_timeout_sec() -> int:
    return _get_int(
        "TRANSCRIBE_POLL_TIMEOUT_SEC",
        TRANSCRIBE_DEFAULT_POLL_TIMEOUT_SEC,
    )


def get_transcribe_request_timeout_sec() -> int:
    return _get_int(
        "TRANSCRIBE_REQUEST_TIMEOUT_SEC",
        TRANSCRIBE_DEFAULT_REQUEST_TIMEOUT_SEC,
    )


def get_allowed_chat_ids() -> set[int]:
    """Chats the bot answers at all; empty means everyone."""

    return _get_int_set("ALLOWED_CHAT_IDS")


def get_admin_chat_id() -> int | None:
    raw_value = os.getenv("ADMIN_CHAT_ID", "").strip()
    try:
        return int(raw_value) if raw_value else None
    except ValueError:
        return None


def _get_int_set(name: str) -> set[int]:
    values: set[int] = set()
    for part in os.getenv(name, "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.add(int(part))
        except ValueError:
            continue
    return values


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default
