from urllib.parse import parse_qs, urlparse


YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}
YOUTUBE_SHORT_HOSTS = {
    "youtu.be",
    "www.youtu.be",
}
VIDEO_ID_LENGTH = 11


def is_youtube_url(url: str) -> bool:
    return extract_video_id(url) is not None


def is_shorts_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc.lower() not in YOUTUBE_HOSTS:
        return False
    return _path_parts(parsed.path)[:1] == ["shorts"]


def extract_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    parts = _path_parts(parsed.path)

    if host in YOUTUBE_SHORT_HOSTS:
        return _valid_id(parts[0]) if parts else None

    if host not in YOUTUBE_HOSTS:
        return None

    if parts[:1] == ["watch"]:
        video_ids = parse_qs(parsed.query).get("v", [])
        return _valid_id(video_ids[0]) if video_ids else None

    if len(parts) >= 2 and parts[0] in {"shorts", "embed", "v", "live"}:
        return _valid_id(parts[1])

    return None


def _path_parts(path: str) -> list[str]:
    return [part for part in path.split("/") if part]


def _valid_id(candidate: str) -> str | None:
    if len(candidate) != VIDEO_ID_LENGTH:
        return None
    if not all(char.isalnum() or char in "-_" for char in candidate):
        return None
    return candidate
