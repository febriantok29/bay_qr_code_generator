#!/usr/bin/env python3
"""
PDF Utilities - Core library and CLI for basic PDF operations.
Uses pypdf (pypdf>=3.0.0). No external system dependencies.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from pypdf import PdfReader, PdfWriter, PageObject, Transformation
from pypdf.errors import PdfReadError


def merge_pdfs(input_paths: List[Path], output_path: Path) -> int:
    """Merge multiple PDFs into one. Returns page count."""
    writer = PdfWriter()
    total_pages = 0
    for path in input_paths:
        try:
            reader = PdfReader(path)
            for page in reader.pages:
                writer.add_page(page)
                total_pages += 1
        except PdfReadError as e:
            raise ValueError(f"Failed to read {path}: {e}") from e
    writer.write(output_path)
    return total_pages


def split_pdf(input_path: Path, output_dir: Path, pages_per_file: int = 1) -> List[Path]:
    """Split PDF into multiple files, N pages each. Returns list of output paths."""
    reader = PdfReader(input_path)
    total = len(reader.pages)
    outputs = []

    for i in range(0, total, pages_per_file):
        writer = PdfWriter()
        end = min(i + pages_per_file, total)
        for page_num in range(i, end):
            writer.add_page(reader.pages[page_num])

        out_path = output_dir / f"{input_path.stem}_part{i // pages_per_file + 1:03d}.pdf"
        writer.write(out_path)
        outputs.append(out_path)

    return outputs


def extract_pages(input_path: Path, output_path: Path, page_numbers: List[int]) -> int:
    """Extract specific pages (1-indexed) to new PDF. Returns page count."""
    reader = PdfReader(input_path)
    total = len(reader.pages)
    writer = PdfWriter()
    count = 0

    for n in page_numbers:
        if 1 <= n <= total:
            writer.add_page(reader.pages[n - 1])
            count += 1
        else:
            raise ValueError(f"Page {n} out of range (1-{total})")

    writer.write(output_path)
    return count


def split_to_single_pages(input_path: Path, output_dir: Path) -> List[Path]:
    """Split PDF into single-page PDFs. Returns list of output paths."""
    return split_pdf(input_path, output_dir, pages_per_file=1)


def rotate_pages(input_path: Path, output_path: Path, page_angles: List[Tuple[int, int]]) -> int:
    """Rotate specific pages. page_angles: list of (page_num_1_indexed, angle_degrees).
    Angle must be multiple of 90. Returns pages modified."""
    reader = PdfReader(input_path)
    writer = PdfWriter()
    modified = 0
    angles = dict(page_angles)

    for i, page in enumerate(reader.pages):
        page_num = i + 1
        if page_num in angles:
            angle = angles[page_num] % 360
            if angle % 90 != 0:
                raise ValueError(f"Angle must be multiple of 90, got {angle}")
            page.rotate(angle)
            modified += 1
        writer.add_page(page)

    writer.write(output_path)
    return modified


def delete_pages(input_path: Path, output_path: Path, page_numbers: List[int]) -> int:
    """Delete specific pages (1-indexed). Returns pages removed."""
    reader = PdfReader(input_path)
    total = len(reader.pages)
    writer = PdfWriter()
    removed = 0
    delete_set = set(page_numbers)

    for i, page in enumerate(reader.pages):
        page_num = i + 1
        if page_num not in delete_set:
            writer.add_page(page)
        else:
            removed += 1

    writer.write(output_path)
    return removed


def extract_text(input_path: Path, output_path: Optional[Path] = None) -> str:
    """Extract text from all pages. Returns text; writes to file if output_path given."""
    reader = PdfReader(input_path)
    texts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            texts.append(text)

    full_text = "\n\n".join(texts)
    if output_path:
        output_path.write_text(full_text, encoding="utf-8")
    return full_text


def pdf_info(input_path: Path) -> dict:
    """Return PDF metadata and page info."""
    reader = PdfReader(input_path)
    meta = reader.metadata or {}
    return {
        "pages": len(reader.pages),
        "title": meta.get("/Title", ""),
        "author": meta.get("/Author", ""),
        "subject": meta.get("/Subject", ""),
        "creator": meta.get("/Creator", ""),
        "producer": meta.get("/Producer", ""),
        "creation_date": meta.get("/CreationDate", ""),
        "modification_date": meta.get("/ModDate", ""),
        "page_sizes": [
            (float(page.mediabox.width), float(page.mediabox.height))
            for page in reader.pages
        ],
    }


def images_to_pdf(image_paths: List[Path], output_path: Path) -> int:
    """Convert images to PDF (one per page). Returns page count."""
    from io import BytesIO

    from pypdf import PdfWriter
    from PIL import Image

    writer = PdfWriter()
    for img_path in image_paths:
        with Image.open(img_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            pdf_bytes = img_to_pdf_bytes(img)
            reader = PdfReader(BytesIO(pdf_bytes))
            writer.add_page(reader.pages[0])

    writer.write(output_path)
    return len(image_paths)


def img_to_pdf_bytes(img) -> bytes:
    """Convert PIL Image to PDF bytes."""
    from io import BytesIO
    from pypdf import PdfWriter

    buf = BytesIO()
    img.save(buf, format="PDF")
    return buf.getvalue()


def pdf_to_images(input_path: Path, output_dir: Path, fmt: str = "PNG", dpi: int = 150) -> List[Path]:
    """Convert PDF pages to images. Requires pdf2image + poppler. Returns list of output paths."""
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise RuntimeError("pdf2image not installed. Install with: pip install pdf2image")

    # Map format to file extension
    ext_map = {"PNG": "png", "JPEG": "jpg", "TIFF": "tiff"}
    ext = ext_map.get(fmt.upper(), fmt.lower())

    images = convert_from_path(input_path, dpi=dpi)
    outputs = []
    for i, img in enumerate(images):
        # JPEG does not support alpha channel; convert RGBA/LA/PA to RGB
        if fmt.upper() == "JPEG" and img.mode in ("RGBA", "LA", "PA", "P"):
            img = img.convert("RGB")
        out_path = output_dir / f"{input_path.stem}_page{i + 1:03d}.{ext}"
        img.save(out_path, fmt)
        outputs.append(out_path)
    return outputs


def main():
    parser = argparse.ArgumentParser(
        description="PDF Utilities - merge, split, extract, rotate, convert",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pdf_utils.py merge file1.pdf file2.pdf -o merged.pdf
  pdf_utils.py split large.pdf -o output_dir -p 2
  pdf_utils.py extract input.pdf -p 1 3 5 -o pages.pdf
  pdf_utils.py rotate input.pdf -o rotated.pdf --rotate 1:90 3:180
  pdf_utils.py delete input.pdf -p 1 2 -o no_first_two.pdf
  pdf_utils.py text input.pdf -o text.txt
  pdf_utils.py info input.pdf
  pdf_utils.py images-to-pdf img1.jpg img2.png -o output.pdf
  pdf_utils.py pdf-to-images input.pdf -o img_dir --dpi 200
        """,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # merge
    p = sub.add_parser("merge", help="Merge multiple PDFs")
    p.add_argument("inputs", nargs="+", type=Path, help="Input PDF files")
    p.add_argument("-o", "--output", type=Path, required=True, help="Output PDF")

    # split
    p = sub.add_parser("split", help="Split PDF into chunks of N pages")
    p.add_argument("input", type=Path, help="Input PDF")
    p.add_argument("-o", "--output-dir", type=Path, required=True, help="Output directory")
    p.add_argument("-p", "--pages", type=int, default=1, help="Pages per output file (default: 1)")

    # split-single (alias for split -p 1)
    p = sub.add_parser("split-single", help="Split PDF into single-page PDFs")
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output-dir", type=Path, required=True)

    # extract
    p = sub.add_parser("extract", help="Extract specific pages to new PDF")
    p.add_argument("input", type=Path)
    p.add_argument("-p", "--pages", nargs="+", type=int, required=True, help="Page numbers (1-indexed)")
    p.add_argument("-o", "--output", type=Path, required=True)

    # rotate
    p = sub.add_parser("rotate", help="Rotate specific pages")
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--rotate", nargs="+", required=True,
                   help="Page:angle pairs (e.g., 1:90 3:180). Angle multiple of 90.")

    # delete
    p = sub.add_parser("delete", help="Delete specific pages")
    p.add_argument("input", type=Path)
    p.add_argument("-p", "--pages", nargs="+", type=int, required=True, help="Page numbers to delete")
    p.add_argument("-o", "--output", type=Path, required=True)

    # text
    p = sub.add_parser("text", help="Extract text from PDF")
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path, help="Output text file (default: stdout)")

    # info
    p = sub.add_parser("info", help="Show PDF metadata and page info")
    p.add_argument("input", type=Path)

    # images-to-pdf
    p = sub.add_parser("images-to-pdf", help="Convert images to PDF")
    p.add_argument("inputs", nargs="+", type=Path, help="Image files")
    p.add_argument("-o", "--output", type=Path, required=True)

    # pdf-to-images
    p = sub.add_parser("pdf-to-images", help="Convert PDF pages to images (requires pdf2image + poppler)")
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output-dir", type=Path, required=True)
    p.add_argument("--fmt", default="PNG", choices=["PNG", "JPEG", "TIFF"], help="Output format")
    p.add_argument("--dpi", type=int, default=150, help="DPI for rendering")

    args = parser.parse_args()

    try:
        if args.cmd == "merge":
            count = merge_pdfs(args.inputs, args.output)
            print(f"Merged {len(args.inputs)} PDFs ({count} pages) -> {args.output}")

        elif args.cmd == "split":
            args.output_dir.mkdir(parents=True, exist_ok=True)
            outputs = split_pdf(args.input, args.output_dir, args.pages)
            print(f"Split into {len(outputs)} files in {args.output_dir}")

        elif args.cmd == "split-single":
            args.output_dir.mkdir(parents=True, exist_ok=True)
            outputs = split_to_single_pages(args.input, args.output_dir)
            print(f"Split into {len(outputs)} single-page PDFs in {args.output_dir}")

        elif args.cmd == "extract":
            count = extract_pages(args.input, args.output, args.pages)
            print(f"Extracted {count} pages -> {args.output}")

        elif args.cmd == "rotate":
            pairs = []
            for pair in args.rotate:
                page_str, angle_str = pair.split(":")
                pairs.append((int(page_str), int(angle_str)))
            count = rotate_pages(args.input, args.output, pairs)
            print(f"Rotated {count} pages -> {args.output}")

        elif args.cmd == "delete":
            count = delete_pages(args.input, args.output, args.pages)
            print(f"Deleted {count} pages -> {args.output}")

        elif args.cmd == "text":
            text = extract_text(args.input, args.output)
            if not args.output:
                print(text)
            else:
                print(f"Extracted text -> {args.output}")

        elif args.cmd == "info":
            info = pdf_info(args.input)
            print(f"Pages: {info['pages']}")
            print(f"Title: {info['title'] or '(none)'}")
            print(f"Author: {info['author'] or '(none)'}")
            print(f"Subject: {info['subject'] or '(none)'}")
            print(f"Creator: {info['creator'] or '(none)'}")
            print(f"Producer: {info['producer'] or '(none)'}")
            print(f"Created: {info['creation_date'] or '(none)'}")
            print(f"Modified: {info['modification_date'] or '(none)'}")
            for i, (w, h) in enumerate(info['page_sizes'], 1):
                print(f"  Page {i}: {w:.0f} x {h:.0f} pts")

        elif args.cmd == "images-to-pdf":
            count = images_to_pdf(args.inputs, args.output)
            print(f"Converted {count} images -> {args.output}")

        elif args.cmd == "pdf-to-images":
            args.output_dir.mkdir(parents=True, exist_ok=True)
            outputs = pdf_to_images(args.input, args.output_dir, args.fmt, args.dpi)
            print(f"Converted {len(outputs)} pages to {args.output_dir}")

    except (ValueError, PdfReadError, RuntimeError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()