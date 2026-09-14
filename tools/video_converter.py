from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

SUPPORTED_TARGET_FORMATS = ["mp4", "mov", "mkv", "webm", "avi", "flv", "wmv"]

_FFMPEG_ARGS: dict[str, list[str]] = {
    "mp4": ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"],
    "mov": ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"],
    "mkv": ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "192k"],
    "webm": ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-c:a", "libopus"],
    "avi": ["-c:v", "mpeg4", "-qscale:v", "5", "-c:a", "libmp3lame", "-b:a", "192k"],
    "flv": ["-c:v", "flv", "-qscale:v", "5", "-c:a", "libmp3lame", "-b:a", "192k"],
    "wmv": ["-c:v", "wmv2", "-qscale:v", "5", "-c:a", "wmav2"],
}


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def convert_video(input_path: Path, output_path: Path, target_format: str) -> tuple[bool, str]:
    args = _FFMPEG_ARGS.get(target_format.lower())
    if args is None:
        return False, f"Format tujuan '{target_format}' tidak didukung."

    command = ["ffmpeg", "-i", str(input_path), *args, "-y", str(output_path)]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        return False, "ffmpeg tidak ditemukan di server."

    if result.returncode != 0:
        return False, (result.stderr or "").strip()[-500:] or "Konversi gagal."
    return True, ""
