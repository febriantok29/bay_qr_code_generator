import io
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app


def _fake_ocr(input_path, output_path, language):
    Path(output_path).write_bytes(b"fake-searchable-pdf")
    return True, ""


def _fake_images_to_pdf(paths, output_path):
    Path(output_path).write_bytes(b"fake-normalized-pdf")


class OcrRouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_get_renders_form(self):
        resp = self.client.get("/ocr")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'name="files"', resp.data)
        self.assertIn(b"multiple", resp.data)
        self.assertIn(b'name="language"', resp.data)

    def test_no_file_flashes_and_redirects(self):
        resp = self.client.post("/ocr", data={}, content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Pilih minimal 1 file".encode(), resp.data)

    @patch("app.ocr_utils.ocr_available", return_value=False)
    def test_missing_dependency_flashes_and_redirects(self, mock_available):
        data = {"files": [(io.BytesIO(b"%PDF-1"), "a.pdf")]}
        resp = self.client.post("/ocr", data=data, content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Tesseract/Ghostscript belum terinstall".encode(), resp.data)

    @patch("app.ocr_utils.ocr_available", return_value=True)
    @patch("app.ocr_utils.ocr_to_searchable_pdf", side_effect=_fake_ocr)
    def test_pdf_input_is_ocred_directly(self, mock_ocr, mock_available):
        data = {"files": [(io.BytesIO(b"%PDF-1"), "scan.pdf")]}
        resp = self.client.post("/ocr", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        mock_ocr.assert_called_once()
        in_path = mock_ocr.call_args[0][0]
        self.assertEqual(in_path.suffix, ".pdf")
        self.assertIn(b"scan_ocr.pdf", resp.data)

    @patch("app.ocr_utils.ocr_available", return_value=True)
    @patch("app.ocr_utils.ocr_to_searchable_pdf", side_effect=_fake_ocr)
    @patch("app.pdf_utils.images_to_pdf", side_effect=_fake_images_to_pdf)
    def test_image_input_is_normalized_to_pdf_first(self, mock_images_to_pdf, mock_ocr, mock_available):
        data = {"files": [(io.BytesIO(b"fake-jpeg"), "foto.jpg")]}
        resp = self.client.post("/ocr", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        mock_images_to_pdf.assert_called_once()
        mock_ocr.assert_called_once()
        in_path = mock_ocr.call_args[0][0]
        self.assertTrue(str(in_path).endswith("_normalized.pdf"))

    @patch("app.ocr_utils.ocr_available", return_value=True)
    @patch("app.ocr_utils.ocr_to_searchable_pdf")
    def test_partial_failure_is_reported(self, mock_ocr, mock_available):
        def side_effect(input_path, output_path, language):
            if "bad" in str(input_path):
                return False, "Tesseract gagal memproses halaman ini"
            return _fake_ocr(input_path, output_path, language)

        mock_ocr.side_effect = side_effect
        data = {
            "files": [
                (io.BytesIO(b"%PDF-1"), "good.pdf"),
                (io.BytesIO(b"%PDF-2"), "bad.pdf"),
            ],
        }
        resp = self.client.post("/ocr", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"bad.pdf", resp.data)
        self.assertIn(b"Tesseract gagal", resp.data)

    @patch("app.ocr_utils.ocr_available", return_value=True)
    @patch("app.ocr_utils.ocr_to_searchable_pdf", side_effect=_fake_ocr)
    def test_duplicate_filenames_get_unique_stems(self, mock_ocr, mock_available):
        data = {
            "files": [
                (io.BytesIO(b"%PDF-1"), "scan.pdf"),
                (io.BytesIO(b"%PDF-2"), "scan.pdf"),
            ],
        }
        resp = self.client.post("/ocr", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        called_stems = sorted(call.args[0].stem for call in mock_ocr.call_args_list)
        self.assertEqual(called_stems, ["scan", "scan-2"])


if __name__ == "__main__":
    unittest.main()
