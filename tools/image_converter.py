import argparse
from pathlib import Path
from PIL import Image

def convert_images(input_dir: Path, output_dir: Path, source_extensions: list[str], target_format: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    target_ext = target_format.lower().lstrip(".")

    format_map = {
        "jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP",
        "tiff": "TIFF", "tif": "TIFF", "bmp": "BMP", "gif": "GIF",
    }
    pil_format = format_map.get(target_ext, target_ext.upper())

    source_exts = {f".{e.lower().lstrip('.')}" for e in source_extensions}
    files = [f for f in input_dir.iterdir() if f.suffix.lower() in source_exts]

    if not files:
        print(f"Tidak ada file dengan ekstensi {source_exts} yang ditemukan di: {input_dir}")
        return

    print(f"Ditemukan {len(files)} file untuk dikonversi -> .{target_ext.upper()}")
    print(f"Folder output: {output_dir}\n")

    success, failed = 0, 0
    for file in sorted(files):
        output_path = output_dir / f"{file.stem}.{target_ext}"
        try:
            with Image.open(file) as img:
                if pil_format == "JPEG" and img.mode in ("RGBA", "P", "LA"):
                    img = img.convert("RGB")
                img.save(output_path, format=pil_format)
            print(f"  [SUKSES] {file.name} -> {output_path.name}")
            success += 1
        except Exception as e:
            print(f"  [GAGAL]  {file.name}: {e}")
            failed += 1

    print(f"\nSelesai. {success} berhasil, {failed} gagal.")

def main() -> None:
    parser = argparse.ArgumentParser(description="Batch image format converter")
    parser.add_argument("--input", type=Path, default=Path("import/image_converter"), help="Folder sumber gambar")
    parser.add_argument("--output", type=Path, default=Path("export/image_converter"), help="Folder output")
    parser.add_argument("--from", dest="source_formats", nargs="+", default=["bmp"], metavar="EXT", help="Ekstensi sumber")
    parser.add_argument("--to", dest="target_format", default="jpg", metavar="EXT", help="Format target")
    args = parser.parse_args()

    convert_images(args.input, args.output, args.source_formats, args.target_format)

if __name__ == "__main__":
    main()
