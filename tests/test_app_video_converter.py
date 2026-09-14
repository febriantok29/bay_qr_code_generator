import io
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app


def _fake_convert_video(input_path, output_path, target_format):
    Path(output_path).write_bytes(b"fake-video-bytes")
    return True, ""


class VideoConverterRouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_get_renders_form(self):
        resp = self.client.get("/video-converter")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'name="videos"', resp.data)
        self.assertIn(b"multiple", resp.data)
        self.assertIn(b'name="target_format"', resp.data)
        self.assertIn(b"MP4", resp.data)
        self.assertIn(b"WMV", resp.data)

    def test_no_file_flashes_and_redirects(self):
        resp = self.client.post(
            "/video-converter", data={}, content_type="multipart/form-data", follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Pilih minimal 1 file video".encode(), resp.data)

    @patch("app.video_converter.ffmpeg_available", return_value=False)
    def test_missing_ffmpeg_flashes_and_redirects(self, mock_available):
        data = {"videos": [(io.BytesIO(b"data"), "a.mov")], "target_format": "mp4"}
        resp = self.client.post(
            "/video-converter", data=data, content_type="multipart/form-data", follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("ffmpeg tidak ditemukan".encode(), resp.data)

    @patch("app.video_converter.ffmpeg_available", return_value=True)
    @patch("app.video_converter.convert_video", side_effect=_fake_convert_video)
    def test_multiple_videos_with_different_names_are_all_converted(self, mock_convert, mock_available):
        data = {
            "videos": [
                (io.BytesIO(b"data1"), "a.mov"),
                (io.BytesIO(b"data2"), "b.mp4"),
            ],
            "target_format": "mkv",
        }
        resp = self.client.post("/video-converter", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_convert.call_count, 2)
        called_stems = sorted(call.args[0].stem for call in mock_convert.call_args_list)
        self.assertEqual(called_stems, ["a", "b"])

    @patch("app.video_converter.ffmpeg_available", return_value=True)
    @patch("app.video_converter.convert_video", side_effect=_fake_convert_video)
    def test_duplicate_filenames_get_unique_stems(self, mock_convert, mock_available):
        data = {
            "videos": [
                (io.BytesIO(b"data1"), "clip.mp4"),
                (io.BytesIO(b"data2"), "clip.mp4"),
            ],
            "target_format": "mkv",
        }
        resp = self.client.post("/video-converter", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        called_stems = sorted(call.args[0].stem for call in mock_convert.call_args_list)
        self.assertEqual(called_stems, ["clip", "clip-2"])

    @patch("app.video_converter.ffmpeg_available", return_value=True)
    @patch("app.video_converter.convert_video")
    def test_partial_failure_is_reported(self, mock_convert, mock_available):
        def side_effect(input_path, output_path, target_format):
            if "bad" in str(input_path):
                return False, "Invalid data found"
            return _fake_convert_video(input_path, output_path, target_format)

        mock_convert.side_effect = side_effect
        data = {
            "videos": [
                (io.BytesIO(b"data1"), "good.mp4"),
                (io.BytesIO(b"data2"), "bad.mp4"),
            ],
            "target_format": "mkv",
        }
        resp = self.client.post("/video-converter", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"bad.mp4", resp.data)
        self.assertIn(b"Invalid data", resp.data)


if __name__ == "__main__":
    unittest.main()
