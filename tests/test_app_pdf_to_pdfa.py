import io
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app


def _fake_ocr(input_path, output_path, language):
    Path(output_path).write_bytes(b"fake-pdfa-bytes")
    return True, ""


class PdfToPdfaRouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_get_renders_form(self):
        resp = self.client.get("/pdf-utils/pdf-to-pdfa")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'name="pdfs"', resp.data)
        self.assertIn(b"multiple", resp.data)
        self.assertIn(b'name="language"', resp.data)

    def test_no_file_flashes_and_redirects(self):
        resp = self.client.post(
            "/pdf-utils/pdf-to-pdfa", data={}, content_type="multipart/form-data", follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Pilih minimal 1 file PDF".encode(), resp.data)

    @patch("app.ocr_utils.ocr_available", return_value=False)
    def test_missing_dependency_flashes_and_redirects(self, mock_available):
        data = {"pdfs": [(io.BytesIO(b"%PDF-1"), "a.pdf")]}
        resp = self.client.post(
            "/pdf-utils/pdf-to-pdfa", data=data, content_type="multipart/form-data", follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Tesseract/Ghostscript belum terinstall".encode(), resp.data)

    @patch("app.ocr_utils.ocr_available", return_value=True)
    @patch("app.ocr_utils.ocr_to_searchable_pdf", side_effect=_fake_ocr)
    def test_multiple_pdfs_are_all_converted(self, mock_ocr, mock_available):
        data = {
            "pdfs": [
                (io.BytesIO(b"%PDF-1"), "a.pdf"),
                (io.BytesIO(b"%PDF-2"), "b.pdf"),
            ],
        }
        resp = self.client.post("/pdf-utils/pdf-to-pdfa", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_ocr.call_count, 2)
        self.assertIn(b"a_pdfa.pdf", resp.data)
        self.assertIn(b"b_pdfa.pdf", resp.data)

    @patch("app.ocr_utils.ocr_available", return_value=True)
    @patch("app.ocr_utils.ocr_to_searchable_pdf", side_effect=_fake_ocr)
    def test_duplicate_filenames_get_unique_stems(self, mock_ocr, mock_available):
        data = {
            "pdfs": [
                (io.BytesIO(b"%PDF-1"), "scan.pdf"),
                (io.BytesIO(b"%PDF-2"), "scan.pdf"),
            ],
        }
        resp = self.client.post("/pdf-utils/pdf-to-pdfa", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        called_stems = sorted(call.args[0].stem for call in mock_ocr.call_args_list)
        self.assertEqual(called_stems, ["scan", "scan-2"])

    @patch("app.ocr_utils.ocr_available", return_value=True)
    @patch("app.ocr_utils.ocr_to_searchable_pdf")
    def test_partial_failure_is_reported(self, mock_ocr, mock_available):
        def side_effect(input_path, output_path, language):
            if "bad" in str(input_path):
                return False, "Ghostscript gagal memproses file ini"
            return _fake_ocr(input_path, output_path, language)

        mock_ocr.side_effect = side_effect
        data = {
            "pdfs": [
                (io.BytesIO(b"%PDF-1"), "good.pdf"),
                (io.BytesIO(b"%PDF-2"), "bad.pdf"),
            ],
        }
        resp = self.client.post("/pdf-utils/pdf-to-pdfa", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"bad.pdf", resp.data)
        self.assertIn(b"Ghostscript gagal", resp.data)


if __name__ == "__main__":
    unittest.main()
