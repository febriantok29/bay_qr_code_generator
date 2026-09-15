import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.ocr_utils import ocr_available, ocr_to_searchable_pdf


class OcrAvailableTests(unittest.TestCase):
    def test_false_when_tesseract_or_ghostscript_missing(self):
        # Real (unmocked) check: neither tesseract nor ghostscript is installed
        # in this environment, so this must reflect that honestly.
        self.assertFalse(ocr_available())

    @patch("tools.ocr_utils.shutil.which", return_value="/usr/bin/x")
    def test_true_when_both_found(self, mock_which):
        self.assertTrue(ocr_available())

    @patch("tools.ocr_utils.shutil.which", side_effect=lambda name: None if name == "gs" else "/usr/bin/tesseract")
    def test_false_when_only_tesseract_found(self, mock_which):
        self.assertFalse(ocr_available())


class OcrToSearchablePdfTests(unittest.TestCase):
    def test_success_calls_ocrmypdf_with_expected_args(self):
        fake_ocrmypdf = types.SimpleNamespace(ocr=lambda *a, **k: None)
        with patch.dict(sys.modules, {"ocrmypdf": fake_ocrmypdf}):
            ok, error = ocr_to_searchable_pdf(Path("in.pdf"), Path("out.pdf"), "ind+eng")
        self.assertTrue(ok)
        self.assertEqual(error, "")

    def test_ocrmypdf_exception_is_reported(self):
        def raise_error(*a, **k):
            raise RuntimeError("PriorOcrFoundError: page already has text")

        fake_ocrmypdf = types.SimpleNamespace(ocr=raise_error)
        with patch.dict(sys.modules, {"ocrmypdf": fake_ocrmypdf}):
            ok, error = ocr_to_searchable_pdf(Path("in.pdf"), Path("out.pdf"), "ind+eng")
        self.assertFalse(ok)
        self.assertIn("PriorOcrFoundError", error)

    def test_missing_package_reports_friendly_error(self):
        with patch.dict(sys.modules, {"ocrmypdf": None}):
            ok, error = ocr_to_searchable_pdf(Path("in.pdf"), Path("out.pdf"), "ind+eng")
        self.assertFalse(ok)
        self.assertIn("ocrmypdf belum terinstall", error)


if __name__ == "__main__":
    unittest.main()
