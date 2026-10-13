from contextlib import contextmanager
from typing import Iterator

from core import cookies
from core.cookies import NETSCAPE_HEADER, cookie_names  # noqa: F401

COOKIE_DOMAIN = ".youtube.com"
COOKIE_LABEL = "YouTube"
REQUIRED_COOKIES = frozenset(
    {
        "SID",
        "HSID",
        "SSID",
        "APISID",
        "SAPISID",
        "__Secure-1PSID",
        "__Secure-3PSID",
        "LOGIN_INFO",
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
