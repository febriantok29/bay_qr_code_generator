import io
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app


def _fake_pdf_to_docx(input_path, output_path):
    Path(output_path).write_bytes(b"fake-docx-bytes")


class PdfToWordRouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_get_renders_form(self):
        resp = self.client.get("/pdf-utils/pdf-to-word")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'name="pdfs"', resp.data)
        self.assertIn(b"multiple", resp.data)

    def test_no_file_flashes_and_redirects(self):
        resp = self.client.post(
            "/pdf-utils/pdf-to-word", data={}, content_type="multipart/form-data", follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Pilih minimal 1 file PDF".encode(), resp.data)

    @patch("app.pdf_utils.pdf_to_docx", side_effect=_fake_pdf_to_docx)
    def test_multiple_pdfs_are_all_converted(self, mock_convert):
        data = {
            "pdfs": [
                (io.BytesIO(b"%PDF-1"), "a.pdf"),
                (io.BytesIO(b"%PDF-2"), "b.pdf"),
            ],
        }
        resp = self.client.post("/pdf-utils/pdf-to-word", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_convert.call_count, 2)
        self.assertIn(b"a.docx", resp.data)
        self.assertIn(b"b.docx", resp.data)

    @patch("app.pdf_utils.pdf_to_docx", side_effect=_fake_pdf_to_docx)
    def test_duplicate_filenames_get_unique_stems(self, mock_convert):
        data = {
            "pdfs": [
                (io.BytesIO(b"%PDF-1"), "scan.pdf"),
                (io.BytesIO(b"%PDF-2"), "scan.pdf"),
            ],
        }
        resp = self.client.post("/pdf-utils/pdf-to-word", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        called_stems = sorted(call.args[0].stem for call in mock_convert.call_args_list)
        self.assertEqual(called_stems, ["scan", "scan-2"])
        self.assertIn(b"scan.docx", resp.data)
        self.assertIn(b"scan-2.docx", resp.data)

    @patch("app.pdf_utils.pdf_to_docx", side_effect=RuntimeError("pdf2docx not installed"))
    def test_missing_dependency_flashes_error(self, mock_convert):
        data = {"pdfs": [(io.BytesIO(b"%PDF-1"), "a.pdf")]}
        resp = self.client.post(
            "/pdf-utils/pdf-to-word", data=data, content_type="multipart/form-data", follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"pdf2docx not installed", resp.data)


if __name__ == "__main__":
    unittest.main()
