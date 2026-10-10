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
    prepare_cookies_file,
)


class PrepareCookiesFileTests(unittest.TestCase):
    def _write(self, content: str) -> str:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
            encoding="utf-8",
        ) as temp_file:
            temp_file.write(content)
            file_path = temp_file.name
        self.addCleanup(os.unlink, file_path)
        return file_path

    def test_netscape_file_is_used_as_is(self) -> None:
        source = self._write(
            f"{NETSCAPE_HEADER}\n.youtube.com\tTRUE\t/\tTRUE\t1\tSID\tx\n"
        )
        self.assertEqual(prepare_cookies_file(source), source)

    def test_cookie_header_is_converted_in_place(self) -> None:
        source = self._write("SID=abc; HSID=def; SID=newer")
        target = prepare_cookies_file(source)

        self.assertEqual(target, source)

        lines = Path(target).read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], NETSCAPE_HEADER)
        self.assertEqual(len(lines), 3)
        values = {line.split("\t")[5]: line.split("\t")[6] for line in lines[1:]}
        self.assertEqual(values, {"SID": "newer", "HSID": "def"})
        self.assertEqual(oct(os.stat(target).st_mode)[-3:], "600")

    def test_conversion_is_idempotent(self) -> None:
        source = self._write("SID=abc; HSID=def")
        first = prepare_cookies_file(source)
        content = Path(first).read_text(encoding="utf-8")
        second = prepare_cookies_file(first)

        self.assertEqual(second, source)
        self.assertEqual(
            Path(second).read_text(encoding="utf-8"),
            content,
        )

    def test_empty_file_returns_none(self) -> None:
        self.assertIsNone(prepare_cookies_file(self._write("   \n")))

    def test_garbage_file_returns_none(self) -> None:
        self.assertIsNone(prepare_cookies_file(self._write("no cookies here")))

    def test_missing_file_returns_none(self) -> None:
        self.assertIsNone(prepare_cookies_file("/nonexistent/cookies.txt"))


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
