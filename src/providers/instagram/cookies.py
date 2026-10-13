from contextlib import contextmanager
from typing import Iterator

from core import cookies

COOKIE_DOMAIN = ".instagram.com"
COOKIE_LABEL = "Instagram"
REQUIRED_COOKIES = frozenset(
    {
        "sessionid",
        "ds_user_id",
        "csrftoken",
    }
)


def materialize_cookies(
    cookie_header: str | None,
    cookies_file: str,
) -> str | None:
    return cookies.materialize_cookies(
        cookie_header,
        cookies_file,
        COOKIE_DOMAIN,
        COOKIE_LABEL,
    )


@contextmanager
def guarded_cookies(file_path: str | None) -> Iterator[None]:
    with cookies.guarded_cookies(file_path, REQUIRED_COOKIES, COOKIE_LABEL):
        yield
