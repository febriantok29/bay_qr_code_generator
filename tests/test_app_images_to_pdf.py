import base64
import io
import re
import unittest
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from app import app


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), color).save(buf, format="PNG")
    return buf.getvalue()


class ImagesToPdfRouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_get_renders_form(self):
        resp = self.client.get("/pdf-utils/images-to-pdf")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'name="images"', resp.data)
        self.assertIn(b"multiple", resp.data)

    def test_no_files_flashes_and_redirects(self):
        resp = self.client.post(
            "/pdf-utils/images-to-pdf", data={}, content_type="multipart/form-data", follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Pilih minimal 1 gambar".encode(), resp.data)

    def test_duplicate_filenames_keep_both_images_distinct(self):
        data = {
            "images": [
                (io.BytesIO(_png_bytes((255, 0, 0))), "photo.png"),
                (io.BytesIO(_png_bytes((0, 0, 255))), "photo.png"),
            ],
        }
        resp = self.client.post("/pdf-utils/images-to-pdf", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)

        match = re.search(rb'data:application/pdf;base64,([A-Za-z0-9+/=]+)"', resp.data)
        self.assertIsNotNone(match)
        pdf_bytes = base64.b64decode(match.group(1))
        reader = PdfReader(io.BytesIO(pdf_bytes))
        self.assertEqual(len(reader.pages), 2)

        colors = []
        for page in reader.pages:
            images = list(page.images)
            self.assertEqual(len(images), 1)
            img = Image.open(io.BytesIO(images[0].data))
            colors.append(img.convert("RGB").getpixel((0, 0)))
        self.assertEqual(len(set(colors)), 2, f"Expected 2 distinct page colors, got {colors}")


if __name__ == "__main__":
    unittest.main()
