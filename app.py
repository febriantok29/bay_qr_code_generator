from __future__ import annotations

import base64
import mimetypes
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for

from tools import (
    csv_merger,
    envelope_label,
    flutter_cleanup,
    image_converter,
    pdf_utils,
    qr_generator,
    remove_bg_utils,
    text_to_spreadsheet,
    webm_to_mp4,
)

app = Flask(__name__)
app.secret_key = "bimbim-utilities-dev"


def to_data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


PREVIEWABLE_IMAGE_MIMES = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp", "image/svg+xml"}


def as_items(paths: list[Path]) -> list[dict]:
    items = []
    for p in paths:
        mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        items.append({
            "name": p.name,
            "data_uri": to_data_uri(p),
            "size": human_size(p.stat().st_size),
            "previewable": mime in PREVIEWABLE_IMAGE_MIMES,
        })
    return items


def make_zip(paths: list[Path], tmpdir: tempfile.TemporaryDirectory, zip_name: str) -> dict:
    zip_dir = Path(tmpdir.name) / "zip_src"
    zip_dir.mkdir(exist_ok=True)
    for p in paths:
        shutil.copy(p, zip_dir / p.name)
    zip_path = Path(shutil.make_archive(str(Path(tmpdir.name) / "result"), "zip", zip_dir))
    return {"name": zip_name, "data_uri": to_data_uri(zip_path)}


def render_page_thumbnails(pdf_path: Path, tmpdir: tempfile.TemporaryDirectory, dpi: int = 70) -> list[dict]:
    thumb_dir = Path(tmpdir.name) / "thumbs"
    thumb_dir.mkdir(exist_ok=True)
    outputs = pdf_utils.pdf_to_images(pdf_path, thumb_dir, "PNG", dpi)
    return [{"page": i, "data_uri": to_data_uri(p)} for i, p in enumerate(outputs, start=1)]


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.0f}TB"


def parse_int_list(raw: str) -> list[int]:
    return [int(p.strip()) for p in raw.replace(",", " ").split() if p.strip()]


def slugify(text: str, max_len: int = 30) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip()).strip("-").lower()
    return (slug or "item")[:max_len]


def safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "", name).strip() or "file"


def output_filename(custom_name: str, default_base: str, ext: str) -> str:
    if custom_name and custom_name.strip():
        name = safe_filename(custom_name.strip())
        return name if name.lower().endswith(f".{ext.lower()}") else f"{name}.{ext}"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{default_base}_{stamp}.{ext}"


@app.route("/")
def index():
    return render_template("index.html")


# ---------------- QR generator ----------------
@app.route("/qr", methods=["GET", "POST"])
def qr_page():
    if request.method == "GET":
        return render_template("qr.html")

    lines = [line.strip() for line in request.form.get("text", "").splitlines() if line.strip()]
    if not lines:
        flash("Teks tidak boleh kosong.")
        return redirect(url_for("qr_page"))

    color_mode = request.form.get("color_mode") == "on"
    tmpdir = tempfile.TemporaryDirectory()
    logo_path = None
    logo_file = request.files.get("logo")
    if logo_file and logo_file.filename:
        logo_path = str(Path(tmpdir.name) / logo_file.filename)
        logo_file.save(logo_path)

    outputs = []
    try:
        for i, text in enumerate(lines, start=1):
            img = qr_generator.build_qr(text, logo_path, color_mode)
            name = "qrcode.png" if len(lines) == 1 else f"{i:02d}_{slugify(text)}.png"
            out_path = Path(tmpdir.name) / name
            img.save(out_path)
            outputs.append(out_path)
    except Exception as e:
        tmpdir.cleanup()
        flash(f"Gagal membuat QR: {e}")
        return redirect(url_for("qr_page"))

    items = as_items(outputs)
    custom_name = request.form.get("filename", "")
    if len(outputs) == 1:
        items[0]["name"] = output_filename(custom_name, f"{slugify(lines[0])}_qr", "png")
        zip_result = None
    else:
        zip_result = make_zip(outputs, tmpdir, output_filename(custom_name, "qrcodes", "zip"))
    tmpdir.cleanup()
    return render_template("qr.html", result={"files": items, "zip": zip_result})


# ---------------- CSV merger ----------------
@app.route("/csv-merger", methods=["GET", "POST"])
def csv_merger_page():
    if request.method == "GET":
        return render_template("csv_merger.html")

    files = [f for f in request.files.getlist("csv_files") if f.filename]
    if not files:
        flash("Pilih minimal 1 file CSV.")
        return redirect(url_for("csv_merger_page"))

    tmpdir = tempfile.TemporaryDirectory()
    paths = []
    for f in files:
        p = Path(tmpdir.name) / f.filename
        f.save(p)
        paths.append(p)

    merged_df = csv_merger.merge_csvs(paths)
    if merged_df.empty:
        tmpdir.cleanup()
        flash("Tidak ada data valid yang bisa digabungkan.")
        return redirect(url_for("csv_merger_page"))

    out_path = Path(tmpdir.name) / "merged.csv"
    merged_df.to_csv(out_path, index=False)
    result = {
        "preview_html": merged_df.head(50).to_html(index=False),
        "total_rows": len(merged_df),
        "shown_rows": min(50, len(merged_df)),
        "data_uri": to_data_uri(out_path),
        "filename": output_filename(request.form.get("filename", ""), "mutasi-gabungan", "csv"),
    }
    tmpdir.cleanup()
    return render_template("csv_merger.html", result=result)


# ---------------- Image converter ----------------
@app.route("/image-converter", methods=["GET", "POST"])
def image_converter_page():
    if request.method == "GET":
        return render_template("image_converter.html")

    files = [f for f in request.files.getlist("images") if f.filename]
    target_format = request.form.get("target_format", "jpg").strip().lower()
    if not files:
        flash("Pilih minimal 1 gambar.")
        return redirect(url_for("image_converter_page"))

    tmpdir = tempfile.TemporaryDirectory()
    input_dir = Path(tmpdir.name) / "input"
    output_dir = Path(tmpdir.name) / "output"
    input_dir.mkdir()

    source_extensions = set()
    for f in files:
        f.save(input_dir / f.filename)
        source_extensions.add(Path(f.filename).suffix.lstrip("."))

    image_converter.convert_images(input_dir, output_dir, list(source_extensions), target_format)

    outputs = sorted(output_dir.iterdir()) if output_dir.exists() else []
    if not outputs:
        tmpdir.cleanup()
        flash("Konversi gagal, tidak ada file dihasilkan.")
        return redirect(url_for("image_converter_page"))

    items = as_items(outputs)
    custom_name = request.form.get("filename", "")
    if len(outputs) == 1:
        if custom_name.strip():
            items[0]["name"] = output_filename(custom_name, "", target_format)
        zip_result = None
    else:
        zip_result = make_zip(outputs, tmpdir, output_filename(custom_name, "gambar-dikonversi", "zip"))
    tmpdir.cleanup()
    return render_template("image_converter.html", result={"files": items, "zip": zip_result})


# ---------------- Envelope label ----------------
@app.route("/envelope-label", methods=["GET", "POST"])
def envelope_label_page():
    if request.method == "GET":
        return render_template("envelope_label.html", presets=envelope_label.SIZE_PRESETS)

    raw_labels = request.form.get("labels", "").splitlines()
    try:
        labels = envelope_label.clean_labels(raw_labels)
    except ValueError as e:
        flash(str(e))
        return redirect(url_for("envelope_label_page"))

    try:
        width_mm = float(request.form.get("width_mm", envelope_label.ENVELOPE_WIDTH_MM))
        height_mm = float(request.form.get("height_mm", envelope_label.ENVELOPE_HEIGHT_MM))
        if width_mm <= 0 or height_mm <= 0:
            raise ValueError
    except ValueError:
        flash("Ukuran amplop tidak valid.")
        return redirect(url_for("envelope_label_page"))

    tmpdir = tempfile.TemporaryDirectory()
    out_path = Path(tmpdir.name) / "envelope_labels.pdf"
    envelope_label.export_pdf(labels, out_path, width_mm, height_mm)
    result = {
        "data_uri": to_data_uri(out_path),
        "filename": output_filename(request.form.get("filename", ""), "label-amplop", "pdf"),
    }
    tmpdir.cleanup()
    return render_template("envelope_label.html", result=result, presets=envelope_label.SIZE_PRESETS)


# ---------------- PDF utils ----------------
@app.route("/pdf-utils")
def pdf_utils_page():
    return render_template("pdf/index.html")


@app.route("/pdf-utils/merge", methods=["GET", "POST"])
def pdf_merge():
    if request.method == "GET":
        return render_template("pdf/merge.html")

    files = [f for f in request.files.getlist("pdfs") if f.filename]
    if len(files) < 2:
        flash("Pilih minimal 2 file PDF untuk digabung.")
        return redirect(url_for("pdf_merge"))

    tmpdir = tempfile.TemporaryDirectory()
    paths = []
    for f in files:
        p = Path(tmpdir.name) / f.filename
        f.save(p)
        paths.append(p)

    out_path = Path(tmpdir.name) / "merged.pdf"
    pdf_utils.merge_pdfs(paths, out_path)
    default_base = f"{Path(files[0].filename).stem}_gabungan"
    result = {
        "data_uri": to_data_uri(out_path),
        "filename": output_filename(request.form.get("filename", ""), default_base, "pdf"),
    }
    tmpdir.cleanup()
    return render_template("pdf/merge.html", result=result)


@app.route("/pdf-utils/split", methods=["GET", "POST"])
def pdf_split():
    if request.method == "GET":
        return render_template("pdf/split.html")

    f = request.files.get("pdf")
    pages_per_file = int(request.form.get("pages_per_file", 1))
    if not f or not f.filename:
        flash("Pilih file PDF.")
        return redirect(url_for("pdf_split"))

    tmpdir = tempfile.TemporaryDirectory()
    in_path = Path(tmpdir.name) / f.filename
    f.save(in_path)
    out_dir = Path(tmpdir.name) / "split"
    out_dir.mkdir()

    outputs = pdf_utils.split_pdf(in_path, out_dir, pages_per_file)
    items = as_items(outputs)
    default_base = f"{in_path.stem}_split"
    zip_result = make_zip(outputs, tmpdir, output_filename(request.form.get("filename", ""), default_base, "zip"))
    tmpdir.cleanup()
    return render_template("pdf/split.html", result={"files": items, "zip": zip_result})


@app.route("/pdf-utils/extract", methods=["GET", "POST"])
def pdf_extract():
    if request.method == "GET":
        return render_template("pdf/extract.html")

    if request.form.get("stage") == "confirm":
        pages_raw = request.form.get("pages", "")
        if not pages_raw.strip():
            flash("Isi nomor halaman yang mau diambil.")
            return redirect(url_for("pdf_extract"))

        tmpdir = tempfile.TemporaryDirectory()
        in_path = Path(tmpdir.name) / "source.pdf"
        in_path.write_bytes(base64.b64decode(request.form["pdf_data"]))
        out_path = Path(tmpdir.name) / "extracted.pdf"

        try:
            pdf_utils.extract_pages(in_path, out_path, parse_int_list(pages_raw))
        except ValueError as e:
            tmpdir.cleanup()
            flash(str(e))
            return redirect(url_for("pdf_extract"))

        source_stem = Path(request.form.get("pdf_name", "dokumen")).stem
        result = {
            "data_uri": to_data_uri(out_path),
            "filename": output_filename(request.form.get("filename", ""), f"{source_stem}_diambil", "pdf"),
        }
        tmpdir.cleanup()
        return render_template("pdf/extract.html", result=result)

    f = request.files.get("pdf")
    if not f or not f.filename:
        flash("Pilih file PDF.")
        return redirect(url_for("pdf_extract"))

    tmpdir = tempfile.TemporaryDirectory()
    in_path = Path(tmpdir.name) / f.filename
    f.save(in_path)

    if request.form.get("action") == "process":
        pages_raw = request.form.get("pages", "")
        if not pages_raw.strip():
            flash("Isi nomor halaman yang mau diambil.")
            tmpdir.cleanup()
            return redirect(url_for("pdf_extract"))
        out_path = Path(tmpdir.name) / "extracted.pdf"
        try:
            pdf_utils.extract_pages(in_path, out_path, parse_int_list(pages_raw))
        except ValueError as e:
            tmpdir.cleanup()
            flash(str(e))
            return redirect(url_for("pdf_extract"))
        result = {
            "data_uri": to_data_uri(out_path),
            "filename": output_filename(request.form.get("filename", ""), f"{in_path.stem}_diambil", "pdf"),
        }
        tmpdir.cleanup()
        return render_template("pdf/extract.html", result=result)

    pdf_b64 = base64.b64encode(in_path.read_bytes()).decode()
    try:
        pages = render_page_thumbnails(in_path, tmpdir)
    except Exception:
        tmpdir.cleanup()
        flash("Preview visual halaman tidak tersedia (butuh Poppler di server). Isi nomor halaman manual, lalu klik \"Ambil Langsung\".")
        return render_template("pdf/extract.html")

    tmpdir.cleanup()
    return render_template("pdf/extract.html", picker={"pdf_b64": pdf_b64, "pdf_name": f.filename, "pages": pages})


@app.route("/pdf-utils/rotate", methods=["GET", "POST"])
def pdf_rotate():
    if request.method == "GET":
        return render_template("pdf/rotate.html")

    if request.form.get("stage") == "confirm":
        rotate_raw = request.form.get("rotate", "")
        if not rotate_raw.strip():
            flash("Isi pasangan halaman:sudut yang mau diputar.")
            return redirect(url_for("pdf_rotate"))

        try:
            pairs = []
            for pair in rotate_raw.replace(",", " ").split():
                page_str, angle_str = pair.split(":")
                pairs.append((int(page_str), int(angle_str)))
        except ValueError:
            flash("Format harus 'halaman:sudut', contoh: 1:90 3:180")
            return redirect(url_for("pdf_rotate"))

        tmpdir = tempfile.TemporaryDirectory()
        in_path = Path(tmpdir.name) / "source.pdf"
        in_path.write_bytes(base64.b64decode(request.form["pdf_data"]))
        out_path = Path(tmpdir.name) / "rotated.pdf"

        try:
            pdf_utils.rotate_pages(in_path, out_path, pairs)
        except ValueError as e:
            tmpdir.cleanup()
            flash(str(e))
            return redirect(url_for("pdf_rotate"))

        source_stem = Path(request.form.get("pdf_name", "dokumen")).stem
        result = {
            "data_uri": to_data_uri(out_path),
            "filename": output_filename(request.form.get("filename", ""), f"{source_stem}_diputar", "pdf"),
        }
        tmpdir.cleanup()
        return render_template("pdf/rotate.html", result=result)

    f = request.files.get("pdf")
    if not f or not f.filename:
        flash("Pilih file PDF.")
        return redirect(url_for("pdf_rotate"))

    tmpdir = tempfile.TemporaryDirectory()
    in_path = Path(tmpdir.name) / f.filename
    f.save(in_path)

    if request.form.get("action") == "process":
        rotate_raw = request.form.get("rotate", "")
        if not rotate_raw.strip():
            flash("Isi pasangan halaman:sudut yang mau diputar.")
            tmpdir.cleanup()
            return redirect(url_for("pdf_rotate"))
        try:
            pairs = []
            for pair in rotate_raw.replace(",", " ").split():
                page_str, angle_str = pair.split(":")
                pairs.append((int(page_str), int(angle_str)))
        except ValueError:
            tmpdir.cleanup()
            flash("Format harus 'halaman:sudut', contoh: 1:90 3:180")
            return redirect(url_for("pdf_rotate"))
        out_path = Path(tmpdir.name) / "rotated.pdf"
        try:
            pdf_utils.rotate_pages(in_path, out_path, pairs)
        except ValueError as e:
            tmpdir.cleanup()
            flash(str(e))
            return redirect(url_for("pdf_rotate"))
        result = {
            "data_uri": to_data_uri(out_path),
            "filename": output_filename(request.form.get("filename", ""), f"{in_path.stem}_diputar", "pdf"),
        }
        tmpdir.cleanup()
        return render_template("pdf/rotate.html", result=result)

    pdf_b64 = base64.b64encode(in_path.read_bytes()).decode()
    try:
        pages = render_page_thumbnails(in_path, tmpdir)
    except Exception:
        tmpdir.cleanup()
        flash("Preview visual halaman tidak tersedia (butuh Poppler di server). Isi pasangan halaman:sudut manual, lalu klik \"Putar Langsung\".")
        return render_template("pdf/rotate.html")

    tmpdir.cleanup()
    return render_template("pdf/rotate.html", picker={"pdf_b64": pdf_b64, "pdf_name": f.filename, "pages": pages})


@app.route("/pdf-utils/delete", methods=["GET", "POST"])
def pdf_delete():
    if request.method == "GET":
        return render_template("pdf/delete.html")

    if request.form.get("stage") == "confirm":
        pages_raw = request.form.get("pages", "")
        if not pages_raw.strip():
            flash("Isi nomor halaman yang mau dihapus.")
            return redirect(url_for("pdf_delete"))

        tmpdir = tempfile.TemporaryDirectory()
        in_path = Path(tmpdir.name) / "source.pdf"
        in_path.write_bytes(base64.b64decode(request.form["pdf_data"]))
        out_path = Path(tmpdir.name) / "deleted.pdf"

        pdf_utils.delete_pages(in_path, out_path, parse_int_list(pages_raw))
        source_stem = Path(request.form.get("pdf_name", "dokumen")).stem
        result = {
            "data_uri": to_data_uri(out_path),
            "filename": output_filename(request.form.get("filename", ""), f"{source_stem}_dihapus", "pdf"),
        }
        tmpdir.cleanup()
        return render_template("pdf/delete.html", result=result)

    f = request.files.get("pdf")
    if not f or not f.filename:
        flash("Pilih file PDF.")
        return redirect(url_for("pdf_delete"))

    tmpdir = tempfile.TemporaryDirectory()
    in_path = Path(tmpdir.name) / f.filename
    f.save(in_path)

    if request.form.get("action") == "process":
        pages_raw = request.form.get("pages", "")
        if not pages_raw.strip():
            flash("Isi nomor halaman yang mau dihapus.")
            tmpdir.cleanup()
            return redirect(url_for("pdf_delete"))
        out_path = Path(tmpdir.name) / "deleted.pdf"
        pdf_utils.delete_pages(in_path, out_path, parse_int_list(pages_raw))
        result = {
            "data_uri": to_data_uri(out_path),
            "filename": output_filename(request.form.get("filename", ""), f"{in_path.stem}_dihapus", "pdf"),
        }
        tmpdir.cleanup()
        return render_template("pdf/delete.html", result=result)

    pdf_b64 = base64.b64encode(in_path.read_bytes()).decode()
    try:
        pages = render_page_thumbnails(in_path, tmpdir)
    except Exception:
        tmpdir.cleanup()
        flash("Preview visual halaman tidak tersedia (butuh Poppler di server). Isi nomor halaman manual, lalu klik \"Hapus Langsung\".")
        return render_template("pdf/delete.html")

    tmpdir.cleanup()
    return render_template("pdf/delete.html", picker={"pdf_b64": pdf_b64, "pdf_name": f.filename, "pages": pages})


@app.route("/pdf-utils/text", methods=["GET", "POST"])
def pdf_extract_text():
    if request.method == "GET":
        return render_template("pdf/text.html")

    f = request.files.get("pdf")
    if not f or not f.filename:
        flash("Pilih file PDF.")
        return redirect(url_for("pdf_extract_text"))

    tmpdir = tempfile.TemporaryDirectory()
    in_path = Path(tmpdir.name) / f.filename
    f.save(in_path)
    out_path = Path(tmpdir.name) / f"{in_path.stem}.txt"

    text = pdf_utils.extract_text(in_path, out_path)
    result = {
        "text": text,
        "data_uri": to_data_uri(out_path),
        "filename": output_filename(request.form.get("filename", ""), in_path.stem, "txt"),
    }
    tmpdir.cleanup()
    return render_template("pdf/text.html", result=result)


@app.route("/pdf-utils/info", methods=["GET", "POST"])
def pdf_info():
    if request.method == "GET":
        return render_template("pdf/info.html")

    f = request.files.get("pdf")
    if not f or not f.filename:
        flash("Pilih file PDF.")
        return redirect(url_for("pdf_info"))

    tmpdir = tempfile.TemporaryDirectory()
    in_path = Path(tmpdir.name) / f.filename
    f.save(in_path)
    info = pdf_utils.pdf_info(in_path)
    tmpdir.cleanup()
    return render_template("pdf/info.html", info=info, info_filename=f.filename)


@app.route("/pdf-utils/images-to-pdf", methods=["GET", "POST"])
def pdf_images_to_pdf():
    if request.method == "GET":
        return render_template("pdf/images_to_pdf.html")

    files = [f for f in request.files.getlist("images") if f.filename]
    if not files:
        flash("Pilih minimal 1 gambar.")
        return redirect(url_for("pdf_images_to_pdf"))

    tmpdir = tempfile.TemporaryDirectory()
    paths = []
    for f in files:
        p = Path(tmpdir.name) / f.filename
        f.save(p)
        paths.append(p)

    out_path = Path(tmpdir.name) / "images.pdf"
    pdf_utils.images_to_pdf(paths, out_path)
    default_base = f"{Path(files[0].filename).stem}_ke-pdf"
    result = {
        "data_uri": to_data_uri(out_path),
        "filename": output_filename(request.form.get("filename", ""), default_base, "pdf"),
    }
    tmpdir.cleanup()
    return render_template("pdf/images_to_pdf.html", result=result)


@app.route("/pdf-utils/pdf-to-images", methods=["GET", "POST"])
def pdf_to_images():
    if request.method == "GET":
        return render_template("pdf/pdf_to_images.html")

    files = [f for f in request.files.getlist("pdfs") if f.filename]
    fmt = request.form.get("fmt", "PNG")
    dpi = int(request.form.get("dpi", 150))
    if not files:
        flash("Pilih minimal 1 file PDF.")
        return redirect(url_for("pdf_to_images"))

    tmpdir = tempfile.TemporaryDirectory()
    seen_stems: dict[str, int] = {}
    in_paths = []
    for f in files:
        stem = Path(f.filename).stem
        seen_stems[stem] = seen_stems.get(stem, 0) + 1
        n = seen_stems[stem]
        unique_stem = stem if n == 1 else f"{stem}-{n}"
        in_path = Path(tmpdir.name) / f"{unique_stem}{Path(f.filename).suffix}"
        f.save(in_path)
        in_paths.append(in_path)

    out_dir = Path(tmpdir.name) / "images"
    out_dir.mkdir()

    outputs = []
    try:
        for in_path in in_paths:
            outputs.extend(pdf_utils.pdf_to_images(in_path, out_dir, fmt, dpi))
    except RuntimeError as e:
        tmpdir.cleanup()
        flash(str(e))
        return redirect(url_for("pdf_to_images"))

    items = as_items(outputs)
    default_base = f"{in_paths[0].stem}_pages" if len(in_paths) == 1 else "pdf_pages"
    zip_result = make_zip(outputs, tmpdir, output_filename(request.form.get("filename", ""), default_base, "zip"))
    tmpdir.cleanup()
    return render_template("pdf/pdf_to_images.html", result={"files": items, "zip": zip_result})


# ---------------- Remove background ----------------
@app.route("/remove-bg", methods=["GET"])
def remove_bg_page():
    formats = remove_bg_utils.supported_extensions(writable=True)
    return render_template("remove_bg.html", formats=formats)


@app.route("/remove-bg/process", methods=["POST"])
def remove_bg_process():
    from flask import jsonify
    from io import BytesIO
    from PIL import Image

    payload = request.get_json(force=True)
    try:
        with Image.open(BytesIO(base64.b64decode(payload["data"]))) as opened:
            image = opened.convert("RGBA")
        extension = payload["format"]
        image_format = "PNG" if extension == "PNG" else remove_bg_utils.format_for_extension(extension)
        target = tuple(payload["target"])
        result = remove_bg_utils.replace_background(image, tuple(payload["source"]), target, int(payload["tolerance"]))
        data = remove_bg_utils.encode_image(result, image_format, target)
        suffix = ".png" if extension == "PNG" else extension
        return jsonify({
            "data": base64.b64encode(data).decode(),
            "extension": suffix,
            "mime": Image.MIME.get(image_format, "application/octet-stream"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------- Text to spreadsheet ----------------
@app.route("/text-to-spreadsheet", methods=["GET", "POST"])
def text_to_spreadsheet_page():
    if request.method == "GET":
        return render_template("text_to_spreadsheet.html")

    raw_text = request.form.get("raw_text", "")
    records = text_to_spreadsheet.parse_records(raw_text)
    if not records:
        flash("Tidak ada transaksi yang bisa diparse dari teks tersebut.")
        return redirect(url_for("text_to_spreadsheet_page"))

    tmpdir = tempfile.TemporaryDirectory()
    csv_path = Path(tmpdir.name) / "transaksi.csv"
    xlsx_path = Path(tmpdir.name) / "transaksi.xlsx"
    text_to_spreadsheet.export_csv(records, csv_path)

    custom_name = request.form.get("filename", "")
    result = {
        "records": records,
        "csv_data_uri": to_data_uri(csv_path),
        "csv_filename": output_filename(custom_name, "transaksi", "csv"),
        "xlsx_data_uri": None,
        "xlsx_filename": output_filename(custom_name, "transaksi", "xlsx"),
    }
    try:
        text_to_spreadsheet.export_xlsx(records, xlsx_path)
        result["xlsx_data_uri"] = to_data_uri(xlsx_path)
    except RuntimeError as e:
        flash(str(e))

    tmpdir.cleanup()
    return render_template("text_to_spreadsheet.html", result=result)


# ---------------- Webm to mp4 ----------------
@app.route("/webm-to-mp4", methods=["GET", "POST"])
def webm_to_mp4_page():
    if request.method == "GET":
        return render_template("webm_to_mp4.html")

    files = [f for f in request.files.getlist("webm") if f.filename]
    if not files:
        flash("Pilih minimal 1 file .webm.")
        return redirect(url_for("webm_to_mp4_page"))

    tmpdir = tempfile.TemporaryDirectory()
    outputs = []
    for f in files:
        in_path = Path(tmpdir.name) / f.filename
        f.save(in_path)
        out_path = Path(tmpdir.name) / f"{in_path.stem}.mp4"
        if webm_to_mp4.convert_webm_to_mp4(in_path, out_path):
            outputs.append(out_path)

    if not outputs:
        tmpdir.cleanup()
        flash("Konversi gagal. Pastikan ffmpeg terpasang di server.")
        return redirect(url_for("webm_to_mp4_page"))

    items = as_items(outputs)
    custom_name = request.form.get("filename", "")
    if len(outputs) == 1:
        if custom_name.strip():
            items[0]["name"] = output_filename(custom_name, "", "mp4")
        zip_result = None
    else:
        zip_result = make_zip(outputs, tmpdir, output_filename(custom_name, "video-dikonversi", "zip"))
    tmpdir.cleanup()
    return render_template("webm_to_mp4.html", result={"files": items, "zip": zip_result})


# ---------------- Flutter build cleanup ----------------
@app.route("/flutter-cleanup/browse")
def flutter_cleanup_browse():
    from flask import jsonify

    raw = request.args.get("path", "").strip()
    try:
        current = Path(raw).expanduser().resolve() if raw else Path.home()
        if not current.is_dir():
            current = Path.home()
    except OSError:
        current = Path.home()

    try:
        dirs = flutter_cleanup.list_subdirs(current)
    except OSError:
        dirs = []

    parent = current.parent
    return jsonify({
        "path": str(current),
        "parent": str(parent) if parent != current else None,
        "dirs": [{"name": d.name, "path": str(d)} for d in dirs],
    })


@app.route("/flutter-cleanup", methods=["GET", "POST"])
def flutter_cleanup_page():
    if request.method == "GET":
        return render_template("flutter_cleanup.html", root=str(Path.home() / "Data"))

    root_raw = request.form.get("root", "").strip()
    try:
        root = Path(root_raw).expanduser().resolve()
        if not root.is_dir():
            raise ValueError("Folder tidak ditemukan.")
    except (ValueError, OSError):
        flash("Path folder tidak valid.")
        return redirect(url_for("flutter_cleanup_page"))

    if request.form.get("stage") == "confirm":
        by_project: dict[str, list[str]] = {}
        for item in request.form.getlist("artifact"):
            proj_str, _, relpath = item.partition("|")
            if proj_str and relpath:
                by_project.setdefault(proj_str, []).append(relpath)

        if not by_project:
            flash("Tidak ada artefak yang dipilih untuk dibersihkan.")
            return redirect(url_for("flutter_cleanup_page"))

        cleaned = []
        total_freed = 0
        for proj_str, relpaths in by_project.items():
            outcome = flutter_cleanup.clean_project(Path(proj_str), relpaths)
            total_freed += outcome["freed_bytes"]
            cleaned.append({"name": Path(proj_str).name, **outcome})
        result = {"cleaned": cleaned, "total_freed": human_size(total_freed)}
        return render_template("flutter_cleanup.html", root=str(root), result=result)

    projects = flutter_cleanup.scan_root(root)
    if not projects:
        flash("Tidak ada proyek Flutter dengan artefak build ditemukan di folder itu.")
        return redirect(url_for("flutter_cleanup_page"))

    for p in projects:
        p["total_size_h"] = human_size(p["total_size"])
        for a in p["artifacts"]:
            a["size_h"] = human_size(a["size"])
    grand_total = human_size(sum(p["total_size"] for p in projects))
    return render_template(
        "flutter_cleanup.html",
        root=str(root),
        preview={"projects": projects, "grand_total": grand_total},
    )


if __name__ == "__main__":
    import os
    app.run(debug=True, port=int(os.environ.get("PORT", 5050)))
