from urllib.parse import ParseResult, urlparse, urlunparse


REDDIT_HOSTS = {
    "reddit.com",
    "www.reddit.com",
    "old.reddit.com",
    "redd.it",
}


def is_reddit_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    return host in REDDIT_HOSTS


def normalize_reddit_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    host = parsed.netloc.lower()
    normalized = ParseResult(
        scheme=scheme,
        netloc=host,
        path=parsed.path or "/",
        params="",
        query=parsed.query,
        fragment="",
    )
    return urlunparse(normalized)
