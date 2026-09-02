import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.remove_bg_utils import replace_background, save_image


class ReplaceBackgroundTests(unittest.TestCase):
    def test_module_does_not_load_tkinter(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import sys, tools.remove_bg_utils; assert 'tkinter' not in sys.modules"],
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_replaces_nearby_opaque_colors_and_preserves_alpha(self) -> None:
        image = Image.new("RGBA", (3, 1))
        image.putdata([(255, 0, 0, 255), (245, 8, 5, 128), (210, 30, 30, 255)])

        result = replace_background(image, (255, 0, 0), (0, 0, 255), 20)

        self.assertEqual(
            list(result.getdata()),
            [(0, 0, 255, 255), (0, 0, 255, 128), (210, 30, 30, 255)],
        )

    def test_saves_png_and_flattens_alpha_for_jpeg(self) -> None:
        image = Image.new("RGBA", (1, 1), (255, 0, 0, 128))

        with tempfile.TemporaryDirectory() as directory:
            png_path = Path(directory) / "result.png"
            jpg_path = Path(directory) / "result.jpg"
            save_image(image, png_path, (255, 255, 255))
            save_image(image, jpg_path, (255, 255, 255))

            with Image.open(png_path) as png:
                self.assertEqual(png.mode, "RGBA")
                self.assertEqual(png.getpixel((0, 0)), (255, 0, 0, 128))
            with Image.open(jpg_path) as jpg:
                self.assertEqual(jpg.mode, "RGB")

    def test_rejects_unsupported_output_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.unsupported"
            with self.assertRaisesRegex(ValueError, "Unsupported output format"):
                save_image(Image.new("RGB", (1, 1)), path, (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
