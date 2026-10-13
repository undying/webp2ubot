from urllib.parse import urlparse


INSTAGRAM_HOSTS = {
    "instagram.com",
    "www.instagram.com",
    "m.instagram.com",
}
MEDIA_KINDS = {"p", "reel", "reels", "tv"}
CANONICAL_KINDS = {"reels": "reel"}
SHORTCODE_MIN_LENGTH = 5
SHORTCODE_MAX_LENGTH = 32


def is_instagram_url(url: str) -> bool:
    return extract_media(url) is not None


def canonical_url(url: str) -> str | None:
    media = extract_media(url)
    if not media:
        return None
    kind, shortcode = media
    return f"https://www.instagram.com/{kind}/{shortcode}/"


def extract_media(url: str) -> tuple[str, str] | None:
    """Return the (kind, shortcode) pair of a post, reel or igtv link."""

    parsed = urlparse(url)
    if parsed.netloc.lower() not in INSTAGRAM_HOSTS:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] in MEDIA_KINDS:
        kind, shortcode = parts[0], parts[1]
    elif len(parts) >= 3 and parts[1] in MEDIA_KINDS:
        kind, shortcode = parts[1], parts[2]
    else:
        return None

    if not _valid_shortcode(shortcode):
        return None
    return CANONICAL_KINDS.get(kind, kind), shortcode


def _valid_shortcode(candidate: str) -> bool:
    if not SHORTCODE_MIN_LENGTH <= len(candidate) <= SHORTCODE_MAX_LENGTH:
        return False
    return all(char.isalnum() or char in "-_" for char in candidate)
