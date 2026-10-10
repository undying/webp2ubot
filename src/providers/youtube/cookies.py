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


def prepare_cookies_file(source_path: str) -> str | None:
    """Normalize the cookies file in place so yt-dlp can persist rotations."""

    try:
        with open(source_path, encoding="utf-8") as source_file:
            content = source_file.read().strip()
    except OSError as exc:
        logger.warning(
            "Cannot read YouTube cookies file=%s",
            source_path,
            exc_info=exc,
        )
        return None

    if not content:
        logger.warning("YouTube cookies file is empty: %s", source_path)
        return None

    if content.startswith("#") or "\t" in content:
        return source_path

    pairs = _parse_cookie_header(content)
    if not pairs:
        logger.warning(
            "YouTube cookies file has unknown format: %s",
            source_path,
        )
        return None

    try:
        _write_netscape_file(source_path, pairs)
    except OSError as exc:
        logger.warning(
            "Cannot rewrite YouTube cookies file=%s",
            source_path,
            exc_info=exc,
        )
        return None

    logger.info(
        "Converted YouTube cookies to Netscape format in place: %s",
        source_path,
    )
    return source_path


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
