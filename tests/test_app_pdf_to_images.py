import io
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app


def _fake_pdf_to_images(input_path, output_dir, fmt, dpi):
    ext = {"PNG": "png", "JPEG": "jpg", "TIFF": "tiff"}.get(fmt.upper(), fmt.lower())
    out_path = Path(output_dir) / f"{input_path.stem}_page001.{ext}"
    out_path.write_bytes(b"fake-image-bytes")
    return [out_path]


class PdfToImagesRouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_get_renders_form(self):
        resp = self.client.get("/pdf-utils/pdf-to-images")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'name="pdfs"', resp.data)
        self.assertIn(b"multiple", resp.data)

    def test_no_file_flashes_and_redirects(self):
        resp = self.client.post(
            "/pdf-utils/pdf-to-images", data={}, content_type="multipart/form-data", follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Pilih minimal 1 file PDF".encode(), resp.data)

    @patch("app.pdf_utils.pdf_to_images", side_effect=_fake_pdf_to_images)
    def test_multiple_pdfs_are_all_converted(self, mock_convert):
        data = {
            "pdfs": [
                (io.BytesIO(b"%PDF-1"), "a.pdf"),
                (io.BytesIO(b"%PDF-2"), "b.pdf"),
            ],
            "fmt": "PNG",
            "dpi": "150",
        }
        resp = self.client.post("/pdf-utils/pdf-to-images", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_convert.call_count, 2)
        self.assertIn(b"a_page001.png", resp.data)
        self.assertIn(b"b_page001.png", resp.data)

    @patch("app.pdf_utils.pdf_to_images", side_effect=_fake_pdf_to_images)
    def test_duplicate_filenames_get_unique_stems(self, mock_convert):
        data = {
            "pdfs": [
                (io.BytesIO(b"%PDF-1"), "scan.pdf"),
                (io.BytesIO(b"%PDF-2"), "scan.pdf"),
            ],
            "fmt": "PNG",
            "dpi": "150",
        }
        resp = self.client.post("/pdf-utils/pdf-to-images", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        called_stems = sorted(call.args[0].stem for call in mock_convert.call_args_list)
        self.assertEqual(called_stems, ["scan", "scan-2"])
        self.assertIn(b"scan_page001.png", resp.data)
        self.assertIn(b"scan-2_page001.png", resp.data)


if __name__ == "__main__":
    unittest.main()
