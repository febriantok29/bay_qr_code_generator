import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.drive_downloader import (
    download_all,
    download_file,
    extract_file_id,
    extract_links,
)


class FakeResponse:
    def __init__(self, status_code=200, headers=None, cookies=None, content=b"", text=""):
        self.status_code = status_code
        self.headers = headers or {}
        self.cookies = cookies or {}
        self._content = content
        self.text = text

    def iter_content(self, chunk_size=1):
        yield self._content


class ExtractFileIdTests(unittest.TestCase):
    def test_file_d_url(self) -> None:
        url = "https://drive.google.com/file/d/1A2B3C4D5E6F7G8H9I0J/view?usp=sharing"
        self.assertEqual(extract_file_id(url), "1A2B3C4D5E6F7G8H9I0J")

    def test_open_id_url(self) -> None:
        url = "https://drive.google.com/open?id=1A2B3C4D5E6F7G8H9I0J"
        self.assertEqual(extract_file_id(url), "1A2B3C4D5E6F7G8H9I0J")

    def test_uc_id_url(self) -> None:
        url = "https://drive.google.com/uc?id=1A2B3C4D5E6F7G8H9I0J&export=download"
        self.assertEqual(extract_file_id(url), "1A2B3C4D5E6F7G8H9I0J")

    def test_non_drive_url_returns_none(self) -> None:
        self.assertIsNone(extract_file_id("https://example.com/file/d/1A2B3C4D5E6F7G8H9I0J"))

    def test_folder_link_returns_none(self) -> None:
        self.assertIsNone(extract_file_id("https://drive.google.com/drive/folders/1A2B3C4D5E6F7G8H9I0J"))

    def test_google_redirect_wrapper_is_unwrapped(self) -> None:
        wrapped = (
            "https://www.google.com/url?q=https://drive.google.com/file/d/"
            "1A2B3C4D5E6F7G8H9I0J/view%3Fusp%3Dsharing&sa=D&source=editors"
        )
        self.assertEqual(extract_file_id(wrapped), "1A2B3C4D5E6F7G8H9I0J")


class ExtractLinksTests(unittest.TestCase):
    def test_parses_sheets_style_pasted_html(self) -> None:
        html = (
            '<google-sheets-html-origin><table><tbody><tr>'
            '<td><a href="https://drive.google.com/file/d/1A2B3C4D5E6F7G8H9I0J/view?usp=sharing">BUKTI</a></td>'
            '<td><a href="https://example.com/not-drive">lain</a></td>'
            '</tr></tbody></table></google-sheets-html-origin>'
        )
        links = extract_links(html)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["file_id"], "1A2B3C4D5E6F7G8H9I0J")
        self.assertEqual(links[0]["label"], "BUKTI")

    def test_dedupes_by_file_id(self) -> None:
        html = (
            '<a href="https://drive.google.com/file/d/1A2B3C4D5E6F7G8H9I0J/view">BUKTI 1</a>'
            '<a href="https://drive.google.com/open?id=1A2B3C4D5E6F7G8H9I0J">BUKTI 1 lagi</a>'
        )
        links = extract_links(html)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["label"], "BUKTI 1")

    def test_empty_html_returns_empty_list(self) -> None:
        self.assertEqual(extract_links(""), [])

    def test_no_drive_links_returns_empty_list(self) -> None:
        html = '<a href="https://example.com/foo">foo</a>'
        self.assertEqual(extract_links(html), [])


class DownloadFileTests(unittest.TestCase):
    def test_success_direct_download(self) -> None:
        response = FakeResponse(
            headers={"Content-Type": "image/jpeg", "Content-Disposition": 'attachment; filename="bukti.jpg"'},
            content=b"filedata",
        )
        session = SimpleNamespace(get=lambda *a, **k: response)
        with tempfile.TemporaryDirectory() as tmp:
            result = download_file(session, "FILEID000001", "BUKTI", Path(tmp))
            self.assertTrue(result["ok"])
            self.assertEqual(result["name"], "bukti.jpg")
            self.assertEqual(result["path"].read_bytes(), b"filedata")

    def test_confirm_token_flow_for_large_file(self) -> None:
        warning = FakeResponse(
            headers={"Content-Type": "text/html; charset=utf-8"},
            cookies={"download_warning_abc123": "TOKEN789"},
            text="<html>Google Drive can't scan this file for viruses.</html>",
        )
        real = FakeResponse(
            headers={"Content-Type": "application/pdf", "Content-Disposition": 'attachment; filename="doc.pdf"'},
            content=b"pdfdata",
        )
        calls = []

        def fake_get(url, params=None, stream=None, timeout=None):
            calls.append(params)
            return real if params.get("confirm") else warning

        session = SimpleNamespace(get=fake_get)
        with tempfile.TemporaryDirectory() as tmp:
            result = download_file(session, "BIGFILEID12", "Video Bukti", Path(tmp))
            self.assertTrue(result["ok"])
            self.assertEqual(result["name"], "doc.pdf")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]["confirm"], "TOKEN789")

    def test_private_or_inaccessible_file_reports_error(self) -> None:
        response = FakeResponse(
            headers={"Content-Type": "text/html"},
            text="<html>You need access</html>",
        )
        session = SimpleNamespace(get=lambda *a, **k: response)
        with tempfile.TemporaryDirectory() as tmp:
            result = download_file(session, "PRIVATEID12", "BUKTI", Path(tmp))
            self.assertFalse(result["ok"])
            self.assertIn("error", result)

    def test_connection_error_reports_error(self) -> None:
        import requests

        def raise_error(*a, **k):
            raise requests.ConnectionError("boom")

        session = SimpleNamespace(get=raise_error)
        with tempfile.TemporaryDirectory() as tmp:
            result = download_file(session, "FILEID000001", "BUKTI", Path(tmp))
            self.assertFalse(result["ok"])

    def test_filename_collision_is_deduped(self) -> None:
        response = FakeResponse(
            headers={"Content-Type": "image/jpeg", "Content-Disposition": 'attachment; filename="bukti.jpg"'},
            content=b"data",
        )
        session = SimpleNamespace(get=lambda *a, **k: response)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            r1 = download_file(session, "FILEID000001", "BUKTI", dest)
            r2 = download_file(session, "FILEID000002", "BUKTI", dest)
            self.assertEqual(r1["name"], "bukti.jpg")
            self.assertEqual(r2["name"], "bukti-2.jpg")


class DownloadAllTests(unittest.TestCase):
    @patch("tools.drive_downloader.requests.Session")
    def test_downloads_every_link(self, mock_session_cls) -> None:
        response = FakeResponse(headers={"Content-Type": "image/png"}, content=b"data")
        mock_session_cls.return_value = SimpleNamespace(get=lambda *a, **k: response)
        links = [
            {"file_id": "IDONE0000001", "label": "BUKTI 1", "url": "u1"},
            {"file_id": "IDTWO0000002", "label": "BUKTI 2", "url": "u2"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            results = download_all(links, Path(tmp))
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["ok"] for r in results))


if __name__ == "__main__":
    unittest.main()
