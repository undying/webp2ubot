import hashlib
import logging
import os
import shutil
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)

NETSCAPE_HEADER = "# Netscape HTTP Cookie File"
COOKIE_DOMAIN = ".youtube.com"
COOKIE_EXPIRY = 2000000000
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
    """Generate the Netscape file from the browser cookie, once per change.

    The file is yt-dlp's working copy: it rotates entries in place, so it is
    only regenerated when YOUTUBE_COOKIE itself changes.
    """

    if not cookie_header:
        if os.path.exists(cookies_file):
            return cookies_file
        return None

    digest = hashlib.sha256(cookie_header.encode("utf-8")).hexdigest()
    digest_path = f"{cookies_file}.source"
    if os.path.exists(cookies_file) and _read_digest(digest_path) == digest:
        return cookies_file

    pairs = _parse_cookie_header(cookie_header)
    if not pairs:
        logger.error("YOUTUBE_COOKIE is set but no cookies could be parsed")
        return cookies_file if os.path.exists(cookies_file) else None

    try:
        os.makedirs(os.path.dirname(cookies_file) or ".", exist_ok=True)
        _write_netscape_file(cookies_file, pairs)
        _write_digest(digest_path, digest)
    except OSError as exc:
        logger.error(
            "Cannot write YouTube cookies file=%s",
            cookies_file,
            exc_info=exc,
        )
        return None

    logger.info(
        "Wrote %s YouTube cookies from YOUTUBE_COOKIE to %s",
        len(pairs),
        cookies_file,
    )
    return cookies_file


def _read_digest(digest_path: str) -> str | None:
    try:
        with open(digest_path, encoding="utf-8") as digest_file:
            return digest_file.read().strip()
    except OSError:
        return None


def _write_digest(digest_path: str, digest: str) -> None:
    with open(digest_path, "w", encoding="utf-8") as digest_file:
        digest_file.write(f"{digest}\n")
    os.chmod(digest_path, 0o600)


def _parse_cookie_header(content: str) -> list[tuple[str, str]]:
    pairs: dict[str, str] = {}
    for chunk in content.replace("\n", " ").split(";"):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        name, _, value = chunk.partition("=")
        pairs[name.strip()] = value.strip()
    return list(pairs.items())


def _write_netscape_file(target_path: str, pairs: list[tuple[str, str]]) -> None:
    temp_path = f"{target_path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as target_file:
        target_file.write(f"{NETSCAPE_HEADER}\n")
        for name, value in pairs:
            target_file.write(
                f"{COOKIE_DOMAIN}\tTRUE\t/\tTRUE\t"
                f"{COOKIE_EXPIRY}\t{name}\t{value}\n"
            )
    os.chmod(temp_path, 0o600)
    os.replace(temp_path, target_path)


def cookie_names(file_path: str) -> set[str]:
    names: set[str] = set()
    try:
        with open(file_path, encoding="utf-8") as cookie_file:
            for line in cookie_file:
                if line.startswith("#"):
                    continue
                fields = line.rstrip("\n").split("\t")
                if len(fields) >= 7:
                    names.add(fields[5])
    except OSError:
        return set()
    return names


@contextmanager
def guarded_cookies(file_path: str | None) -> Iterator[None]:
    """Roll the cookies file back if yt-dlp drops authentication cookies."""

    if not file_path:
        yield
        return

    names_before = cookie_names(file_path)
    backup_path = f"{file_path}.bak"
    try:
        owner_stat = os.stat(file_path)
        shutil.copy2(file_path, backup_path)
    except OSError:
        yield
        return

    try:
        yield
    finally:
        names_after = cookie_names(file_path)
        lost = (names_before & REQUIRED_COOKIES) - names_after
        if lost:
            logger.error(
                "yt-dlp dropped auth cookies %s, restoring previous file",
                sorted(lost),
            )
            os.replace(backup_path, file_path)
        else:
            if names_after != names_before:
                logger.info(
                    "YouTube cookies rotated, %s entries",
                    len(names_after),
                )
            try:
                os.unlink(backup_path)
            except OSError:
                pass
        _restore_ownership(file_path, owner_stat)


def _restore_ownership(file_path: str, owner_stat: os.stat_result) -> None:
    """yt-dlp rewrites the file as the container user, locking out the host."""

    try:
        current = os.stat(file_path)
        if (current.st_uid, current.st_gid) != (
            owner_stat.st_uid,
            owner_stat.st_gid,
        ):
            os.chown(file_path, owner_stat.st_uid, owner_stat.st_gid)
        if current.st_mode != owner_stat.st_mode:
            os.chmod(file_path, owner_stat.st_mode)
    except OSError as exc:
        logger.warning(
            "Cannot restore ownership of cookies file=%s",
            file_path,
            exc_info=exc,
        )
