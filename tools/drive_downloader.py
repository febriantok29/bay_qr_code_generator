from __future__ import annotations

import mimetypes
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import requests

DRIVE_HOSTS = {"drive.google.com", "docs.google.com"}
DRIVE_DOWNLOAD_URL = "https://drive.google.com/uc"
DOWNLOAD_TIMEOUT = 30

_FILE_D_RE = re.compile(r"/file/d/([a-zA-Z0-9_-]{10,})")
_DISPOSITION_RE = re.compile(r'filename\*?=(?:UTF-8\'\')?"?([^";\n]+)"?')
_CONFIRM_RE = re.compile(r"confirm=([0-9A-Za-z_-]+)")


def _unwrap_google_redirect(url: str) -> str:
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    if parsed.netloc in {"www.google.com", "google.com"} and parsed.path == "/url":
        target = parse_qs(parsed.query).get("q")
        if target:
            return target[0]
    return url


def extract_file_id(url: str) -> str | None:
    url = _unwrap_google_redirect(url)
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.netloc not in DRIVE_HOSTS:
        return None
    match = _FILE_D_RE.search(parsed.path)
    if match:
        return match.group(1)
    qs = parse_qs(parsed.query)
    if qs.get("id"):
        return qs["id"][0]
    return None


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append({"href": self._href, "text": "".join(self._text).strip()})
            self._href = None
            self._text = []


def extract_links(html: str) -> list[dict]:
    if not html:
        return []
    parser = _LinkParser()
    parser.feed(html)
    seen: set[str] = set()
    result = []
    for link in parser.links:
        file_id = extract_file_id(link["href"])
        if not file_id or file_id in seen:
            continue
        seen.add(file_id)
        result.append({"file_id": file_id, "label": link["text"] or file_id, "url": link["href"]})
    return result


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip()).strip("-").lower()
    return (slug or "file")[:max_len]


def _dedupe_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix, counter = path.stem, path.suffix, 2
    while True:
        candidate = path.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _filename_from_response(response: requests.Response, fallback: str) -> str:
    disposition = response.headers.get("Content-Disposition", "")
    match = _DISPOSITION_RE.search(disposition)
    if match:
        name = unquote(match.group(1).strip())
        if name:
            return name
    content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
    ext = mimetypes.guess_extension(content_type) if content_type else None
    return f"{fallback}{ext or ''}"


def _looks_like_error_page(response: requests.Response) -> bool:
    return response.headers.get("Content-Type", "").startswith("text/html")


def _get_confirm_token(response: requests.Response) -> str | None:
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            return value
    match = _CONFIRM_RE.search(response.text[:4000]) if response.text else None
    return match.group(1) if match else None


def download_file(session: requests.Session, file_id: str, label: str, dest_dir: Path) -> dict:
    try:
        response = session.get(
            DRIVE_DOWNLOAD_URL, params={"id": file_id, "export": "download"},
            stream=True, timeout=DOWNLOAD_TIMEOUT,
        )
    except requests.RequestException as e:
        return {"ok": False, "file_id": file_id, "label": label, "error": f"Gagal konek: {e}"}

    if response.status_code != 200:
        return {"ok": False, "file_id": file_id, "label": label, "error": f"HTTP {response.status_code}"}

    if _looks_like_error_page(response):
        token = _get_confirm_token(response)
        if not token:
            return {"ok": False, "file_id": file_id, "label": label, "error": "Tidak bisa diakses (private, dihapus, atau link tidak valid)."}
        try:
            response = session.get(
                DRIVE_DOWNLOAD_URL, params={"id": file_id, "export": "download", "confirm": token},
                stream=True, timeout=DOWNLOAD_TIMEOUT,
            )
        except requests.RequestException as e:
            return {"ok": False, "file_id": file_id, "label": label, "error": f"Gagal konek: {e}"}
        if _looks_like_error_page(response):
            return {"ok": False, "file_id": file_id, "label": label, "error": "Tidak bisa diakses (private, dihapus, atau link tidak valid)."}

    fallback_name = f"{_slugify(label)}-{file_id[:8]}"
    dest_path = _dedupe_path(dest_dir / _filename_from_response(response, fallback_name))

    try:
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
    except requests.RequestException as e:
        dest_path.unlink(missing_ok=True)
        return {"ok": False, "file_id": file_id, "label": label, "error": f"Gagal download: {e}"}

    if dest_path.stat().st_size == 0:
        dest_path.unlink(missing_ok=True)
        return {"ok": False, "file_id": file_id, "label": label, "error": "File kosong / tidak bisa diakses."}

    return {
        "ok": True,
        "file_id": file_id,
        "label": label,
        "path": dest_path,
        "name": dest_path.name,
        "size": dest_path.stat().st_size,
    }


def download_all(links: list[dict], dest_dir: Path) -> list[dict]:
    session = requests.Session()
    return [download_file(session, link["file_id"], link["label"], dest_dir) for link in links]
