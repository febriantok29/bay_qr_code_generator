from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Iterable
from PIL import Image, ImageDraw, ImageFont

LABELS = [
    "Khatib",
    "Ust. Atep",
    "Marbot",
    "Muazin",
    "Muazin",
    "Bilal",
]

ENVELOPE_WIDTH_MM = 92
ENVELOPE_HEIGHT_MM = 165
PRINT_DPI = 300
MARGIN_MM = 5
TEXT_ORIENTATION = "vertical"

SIZE_PRESETS = {
    "panjang": ("Amplop Panjang (92 × 165 mm)", 92, 165),
    "dl": ("Amplop DL (110 × 220 mm)", 110, 220),
    "c6": ("Amplop C6 (114 × 162 mm)", 114, 162),
    "c5": ("Amplop C5 (162 × 229 mm)", 162, 229),
}


def mm_to_px(mm: float, dpi: int) -> int:
    return round(mm / 25.4 * dpi)

def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]

    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size=size)
        except OSError:
            continue

    return ImageFont.load_default()

def fit_font_for_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width_px: int,
    max_height_px: int,
    orientation: str,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for size in range(140, 9, -2):
        font = load_font(size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        text_w = right - left
        text_h = bottom - top

        if orientation == "vertical":
            fits = text_h <= max_width_px and text_w <= max_height_px
        else:
            fits = text_w <= max_width_px and text_h <= max_height_px

        if fits:
            return font

    return load_font(10)

def build_page(
    text: str,
    width_px: int,
    height_px: int,
    margin_px: int,
    orientation: str,
) -> Image.Image:
    image = Image.new("RGB", (width_px, height_px), "white")
    draw = ImageDraw.Draw(image)

    printable_w = width_px - (margin_px * 2)
    printable_h = height_px - (margin_px * 2)

    font = fit_font_for_text(draw, text, printable_w, printable_h, orientation)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    text_w = right - left
    text_h = bottom - top

    if orientation == "vertical":
        text_layer = Image.new("RGBA", (text_w, text_h), (255, 255, 255, 0))
        text_draw = ImageDraw.Draw(text_layer)
        text_draw.text((-left, -top), text, fill="black", font=font)
        rotated = text_layer.rotate(270, expand=True)

        x = (width_px - rotated.width) // 2
        y = (height_px - rotated.height) // 2
        image.paste(rotated, (x, y), rotated)
    else:
        x = (width_px - text_w) // 2
        y = (height_px - text_h) // 2
        draw.text((x, y), text, fill="black", font=font)

    return image

def clean_labels(raw_labels: Iterable[str]) -> list[str]:
    labels = [label.strip() for label in raw_labels if label and label.strip()]
    if not labels:
        raise ValueError("Label kosong. Isi minimal 1 teks.")
    return labels

def export_pdf(
    labels: list[str],
    output_pdf: Path,
    width_mm: float = ENVELOPE_WIDTH_MM,
    height_mm: float = ENVELOPE_HEIGHT_MM,
) -> Path:
    width_px = mm_to_px(width_mm, PRINT_DPI)
    height_px = mm_to_px(height_mm, PRINT_DPI)
    margin_px = mm_to_px(MARGIN_MM, PRINT_DPI)

    pages = [build_page(text, width_px, height_px, margin_px, TEXT_ORIENTATION) for text in labels]
    first_page, rest_pages = pages[0], pages[1:]

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    first_page.save(
        output_pdf,
        "PDF",
        resolution=PRINT_DPI,
        save_all=True,
        append_images=rest_pages,
    )
    return output_pdf

def main() -> None:
    labels = clean_labels(LABELS)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path("export") / f"envelope_labels_{timestamp}.pdf"
    pdf_file = export_pdf(labels, output_path)

    print("PDF berhasil dibuat")
    print(f"Jumlah halaman: {len(labels)}")
    print(f"Ukuran per halaman: {ENVELOPE_WIDTH_MM} x {ENVELOPE_HEIGHT_MM} mm")
    print(f"Lokasi file: {pdf_file}")

if __name__ == "__main__":
    main()
