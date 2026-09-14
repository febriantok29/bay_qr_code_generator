import unittest
from pathlib import Path
from unittest.mock import patch

from tools.video_converter import convert_video, ffmpeg_available


class FfmpegAvailableTests(unittest.TestCase):
    @patch("tools.video_converter.shutil.which", return_value="/usr/bin/ffmpeg")
    def test_true_when_found(self, mock_which):
        self.assertTrue(ffmpeg_available())

    @patch("tools.video_converter.shutil.which", return_value=None)
    def test_false_when_missing(self, mock_which):
        self.assertFalse(ffmpeg_available())


class ConvertVideoTests(unittest.TestCase):
    def test_unsupported_format_returns_error_without_calling_subprocess(self):
        with patch("tools.video_converter.subprocess.run") as mock_run:
            ok, error = convert_video(Path("in.mov"), Path("out.xyz"), "xyz")
        self.assertFalse(ok)
        self.assertIn("tidak didukung", error)
        mock_run.assert_not_called()

    @patch("tools.video_converter.subprocess.run")
    def test_success_returns_true(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""
        ok, error = convert_video(Path("in.mov"), Path("out.mp4"), "mp4")
        self.assertTrue(ok)
        self.assertEqual(error, "")
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "ffmpeg")
        self.assertIn("-i", args)
        self.assertIn(str(Path("in.mov")), args)
        self.assertIn(str(Path("out.mp4")), args)

    @patch("tools.video_converter.subprocess.run")
    def test_nonzero_returncode_reports_stderr(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Invalid data found when processing input"
        ok, error = convert_video(Path("in.mov"), Path("out.mp4"), "mp4")
        self.assertFalse(ok)
        self.assertIn("Invalid data", error)

    @patch("tools.video_converter.subprocess.run", side_effect=FileNotFoundError)
    def test_missing_ffmpeg_binary_reports_error(self, mock_run):
        ok, error = convert_video(Path("in.mov"), Path("out.mp4"), "mp4")
        self.assertFalse(ok)
        self.assertIn("ffmpeg tidak ditemukan", error)


if __name__ == "__main__":
    unittest.main()
