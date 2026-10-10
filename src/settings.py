import os


REDDIT_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) "
    "Gecko/20100101 Firefox/149.0"
)
YOUTUBE_DEFAULT_MAX_DURATION_SEC = 600
YOUTUBE_DEFAULT_MAX_FILESIZE_MB = 48


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


def get_youtube_cookies_file() -> str | None:
    cookies_file = os.getenv("YOUTUBE_COOKIES_FILE")
    if cookies_file and os.path.exists(cookies_file):
        return cookies_file
    return None


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default
