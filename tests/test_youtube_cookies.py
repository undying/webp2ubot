import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from providers.youtube.cookies import (
    NETSCAPE_HEADER,
    cookie_names,
    guarded_cookies,
    materialize_cookies,
)


COOKIE_HEADER = "SID=abc; HSID=def; LOGIN_INFO=ghi"


class MaterializeCookiesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work_dir = tempfile.mkdtemp()
        self.cookies_file = os.path.join(self.work_dir, "youtube_cookies.txt")
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        for name in os.listdir(self.work_dir):
            os.unlink(os.path.join(self.work_dir, name))
        os.rmdir(self.work_dir)

    def test_writes_netscape_file_from_cookie_header(self) -> None:
        result = materialize_cookies(COOKIE_HEADER, self.cookies_file)

        self.assertEqual(result, self.cookies_file)
        lines = Path(result).read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], NETSCAPE_HEADER)
        self.assertEqual(cookie_names(result), {"SID", "HSID", "LOGIN_INFO"})
        self.assertEqual(oct(os.stat(result).st_mode)[-3:], "600")

    def test_unchanged_cookie_keeps_rotated_file(self) -> None:
        materialize_cookies(COOKIE_HEADER, self.cookies_file)
        rotated = Path(self.cookies_file).read_text(
            encoding="utf-8"
        ).replace("abc", "rotated-by-ytdlp")
        Path(self.cookies_file).write_text(rotated, encoding="utf-8")

        materialize_cookies(COOKIE_HEADER, self.cookies_file)

        self.assertIn(
            "rotated-by-ytdlp",
            Path(self.cookies_file).read_text(encoding="utf-8"),
        )

    def test_changed_cookie_regenerates_file(self) -> None:
        materialize_cookies(COOKIE_HEADER, self.cookies_file)
        materialize_cookies("SID=new; YSC=zzz", self.cookies_file)

        self.assertEqual(cookie_names(self.cookies_file), {"SID", "YSC"})

    def test_missing_cookie_keeps_existing_file(self) -> None:
        materialize_cookies(COOKIE_HEADER, self.cookies_file)
        result = materialize_cookies(None, self.cookies_file)

        self.assertEqual(result, self.cookies_file)
        self.assertEqual(cookie_names(result), {"SID", "HSID", "LOGIN_INFO"})

    def test_missing_cookie_and_no_file_returns_none(self) -> None:
        self.assertIsNone(materialize_cookies(None, self.cookies_file))

    def test_garbage_cookie_returns_none(self) -> None:
        self.assertIsNone(
            materialize_cookies("no cookies here", self.cookies_file)
        )

    def test_creates_parent_directory(self) -> None:
        nested = os.path.join(self.work_dir, "secrets", "cookies.txt")
        result = materialize_cookies(COOKIE_HEADER, nested)

        self.assertEqual(result, nested)
        self.addCleanup(os.rmdir, os.path.dirname(nested))
        self.addCleanup(os.unlink, f"{nested}.source")
        self.addCleanup(os.unlink, nested)


class GuardedCookiesTests(unittest.TestCase):
    def _write_netscape(self, names: list[str]) -> str:
        lines = [NETSCAPE_HEADER]
        for name in names:
            lines.append(f".youtube.com\tTRUE\t/\tTRUE\t1\t{name}\tvalue")
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
            encoding="utf-8",
        ) as temp_file:
            temp_file.write("\n".join(lines) + "\n")
            file_path = temp_file.name
        self.addCleanup(os.unlink, file_path)
        return file_path

    def test_restores_file_when_auth_cookies_disappear(self) -> None:
        path = self._write_netscape(["SID", "HSID", "LOGIN_INFO", "YSC"])
        original = Path(path).read_text(encoding="utf-8")

        with guarded_cookies(path):
            Path(path).write_text(
                f"{NETSCAPE_HEADER}\n.youtube.com\tTRUE\t/\tTRUE\t1\tYSC\tv\n",
                encoding="utf-8",
            )

        self.assertEqual(Path(path).read_text(encoding="utf-8"), original)
        self.assertFalse(os.path.exists(f"{path}.bak"))

    def test_keeps_rotated_file_when_auth_cookies_survive(self) -> None:
        path = self._write_netscape(["SID", "HSID", "LOGIN_INFO", "YSC"])

        with guarded_cookies(path):
            rotated = Path(path).read_text(encoding="utf-8").replace(
                "\tvalue",
                "\trotated",
            )
            Path(path).write_text(rotated, encoding="utf-8")

        self.assertIn("rotated", Path(path).read_text(encoding="utf-8"))
        self.assertEqual(
            cookie_names(path),
            {"SID", "HSID", "LOGIN_INFO", "YSC"},
        )
        self.assertFalse(os.path.exists(f"{path}.bak"))

    def test_restores_file_when_body_raises(self) -> None:
        path = self._write_netscape(["SID", "HSID", "LOGIN_INFO"])
        original = Path(path).read_text(encoding="utf-8")

        with self.assertRaises(RuntimeError):
            with guarded_cookies(path):
                Path(path).write_text(NETSCAPE_HEADER + "\n", encoding="utf-8")
                raise RuntimeError("boom")

        self.assertEqual(Path(path).read_text(encoding="utf-8"), original)

    def test_restores_permissions_after_rewrite(self) -> None:
        path = self._write_netscape(["SID", "HSID", "LOGIN_INFO"])
        os.chmod(path, 0o600)

        with guarded_cookies(path):
            Path(path).write_text(
                Path(path).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            os.chmod(path, 0o644)

        self.assertEqual(oct(os.stat(path).st_mode)[-3:], "600")

    def test_no_cookies_file_is_a_noop(self) -> None:
        with guarded_cookies(None):
            pass


if __name__ == "__main__":
    unittest.main()
