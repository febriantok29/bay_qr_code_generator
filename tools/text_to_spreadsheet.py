import argparse
import csv
import importlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any

VALUES = """
RI

Retail IRL ITUNES.COM APPLE.COM/BILL

14 Jun 2026

-Rp169.000
P

PAYMENT_KKCB_TKP***1234_***1234

16 Jun 2026

+Rp3.474.772
RU

Retail USA GITHUB.COM GITHUB, INC.

18 Jun 2026

-Rp177.580
icon

Retail IDN Jakarta PT Tokopedia

20 Jun 2026

-Rp52.000
RI

Retail IDN JAKARTA BARAT ALFAMART K198 T

20 Jun 2026

-Rp71.700
RI

Retail IDN Jakarta Selat GoPayQRESBRESTA

21 Jun 2026

-Rp68.000
RI

Retail IDN JAKARTA BARAT OMG TANJUNG DUR

22 Jun 2026

-Rp545.000
icon

Retail IDN Jakarta PT Tokopedia

22 Jun 2026

-Rp203.100
RI

Retail IDN Jakarta Selat GoPayQRKOPINAKO

24 Jun 2026

-Rp91.300
RI

Retail IDN Jakarta Selat GoPayQRMCDONALD

24 Jun 2026

-Rp101.500
RI

Retail IDN Jakarta Selat GoPayQRMCDONALD

24 Jun 2026

-Rp46.000
icon

TOKOPEDIA_CYBS_CCL03 : 3/3

27 Jun 2026

-Rp196.366
icon

Retail IDN Jakarta PT Tokopedia

30 Jun 2026

-Rp426.990
RI

Retail IRL ITUNES.COM APPLE.COM/BILL

4 Jul 2026

-Rp349.000
RI

Retail IDN Jakarta Selat GoPayQRMartabak

4 Jul 2026

-Rp28.000
icon

PT Tokopedia : 2/3

5 Jul 2026

-Rp95.471
RI

Retail IDN Jakarta Selat GoPayQRMOEDACOF

5 Jul 2026

-Rp216.300
RI

Retail IRL ITUNES.COM APPLE.COM/BILL

8 Jul 2026

-Rp49.000
OT

OMG TANJUNG DUREN : 0/3

9 Jul 2026

+Rp545.000
OT

OMG TANJUNG DUREN : 1/3

9 Jul 2026

-Rp181.667
CI

Credit IRL ITUNES.COM APPLE.COM/BILL

9 Jul 2026

+Rp169.000
BA

BIAYA ADMIN BRING OMG TANJUNG DUREN

9 Jul 2026

-Rp50.000
icon

Retail IDN Jakarta PT Tokopedia

11 Jul 2026

-Rp50.500
RI

Retail IDN Jakarta Selat GoPayQRWarmindo

12 Jul 2026

-Rp20.000
RI

Retail IDN JAKARTA SELAT GOJEK RECURRING

12 Jul 2026

-Rp49.100
RI

Retail IDN JAKARTA SELAT GOJEK RECURRING

12 Jul 2026

-Rp51.700
icon

Retail IDN Jakarta PT Tokopedia

14 Jul 2026

-Rp52.000
EF

E-STATEMENT FEE

15 Jul 2026

-Rp5.000
"""

MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "Mei": "05", "Jun": "06", "Jul": "07", "Agu": "08",
    "Sep": "09", "Okt": "10", "Nov": "11", "Des": "12",
}

def parse_amount(raw: str) -> int:
    if not raw:
        return 0
    cleaned = raw.strip().replace("Rp", "").replace(".", "")
    sign = -1 if cleaned.startswith("-") else 1
    numeric = cleaned.lstrip("+-")
    return sign * int(numeric) if numeric.isdigit() else 0

def parse_date(raw: str) -> datetime:
    parts = raw.strip().split()
    if len(parts) == 3:
        day, month, year = parts
        month_num = MONTH_MAP.get(month.capitalize(), month)
        return datetime.strptime(f"{day} {month_num} {year}", "%d %m %Y")
    return datetime.strptime(raw.strip(), "%d %b %Y")

def parse_records(raw_text: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    records: list[dict[str, Any]] = []
    
    date_pattern = re.compile(r"^\d{1,2}\s+[a-zA-Z]+\s+\d{4}$")

    index = 0
    while index < len(lines):
        if date_pattern.match(lines[index]):
            if index >= 2:
                initial = lines[index - 2]
                description = lines[index - 1]
                date_text = lines[index]

                amount_text = ""
                if index + 1 < len(lines) and lines[index + 1].startswith(("-Rp", "+Rp")):
                    amount_text = lines[index + 1]
                    index += 2
                else:
                    index += 1

                try:
                    parsed_date = parse_date(date_text)
                    parsed_amount = parse_amount(amount_text)
                except ValueError:
                    continue

                records.append({
                    "initial": initial,
                    "description": description,
                    "date": parsed_date.strftime("%Y-%m-%d"),
                    "amount_raw": amount_text or "Rp0",
                    "amount": parsed_amount,
                    "type": "kredit" if parsed_amount > 0 else "debit",
                })
            else:
                index += 1
        else:
            index += 1

    return records

def export_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["initial", "description", "date", "amount_raw", "amount", "type"]
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def export_xlsx(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        openpyxl = importlib.import_module("openpyxl")
    except ImportError as exc:
        raise RuntimeError(
            "Untuk export .xlsx, install dulu: pip install openpyxl"
        ) from exc

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Transaksi"

    headers = ["initial", "description", "date", "amount_raw", "amount", "type"]
    sheet.append(headers)
    for row in rows:
        sheet.append([row[h] for h in headers])

    workbook.save(output_path)

def main() -> None:
    default_filename = datetime.now().strftime("export/%Y-%m-%d %H.%M - transaksi.xlsx")
    
    parser = argparse.ArgumentParser(
        description="Parse text transaksi dan export ke spreadsheet."
    )
    parser.add_argument(
        "--output",
        default=default_filename,
        help=f"Path output file. Gunakan .xlsx atau .csv (default: {default_filename})",
    )
    args = parser.parse_args()

    records = parse_records(VALUES)
    if not records:
        raise SystemExit("Tidak ada record valid yang berhasil diparse.")

    output_path = Path(args.output)
    suffix = output_path.suffix.lower()

    if suffix == ".csv":
        export_csv(records, output_path)
    elif suffix == ".xlsx":
        export_xlsx(records, output_path)
    else:
        raise SystemExit("Format output tidak didukung. Gunakan .xlsx atau .csv")

    print(f"Berhasil export {len(records)} transaksi ke: {output_path.absolute()}")

if __name__ == "__main__":
    main()