import tempfile
import unittest
from pathlib import Path

from docx import Document
from reportlab.pdfgen import canvas

from tools.pdf_utils import pdf_to_docx


class PdfToDocxTests(unittest.TestCase):
    def test_converts_text_pdf_to_readable_docx(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "sample.pdf"
            docx_path = Path(tmp) / "sample.docx"

            c = canvas.Canvas(str(pdf_path))
            c.drawString(100, 750, "Halo dunia, ini contoh dokumen PDF sederhana.")
            c.save()

            pdf_to_docx(pdf_path, docx_path)

            self.assertTrue(docx_path.exists())
            doc = Document(str(docx_path))
            text = "\n".join(p.text for p in doc.paragraphs)
            self.assertIn("Halo dunia", text)


if __name__ == "__main__":
    unittest.main()
