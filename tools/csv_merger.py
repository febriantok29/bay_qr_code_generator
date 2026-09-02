import pandas as pd
import glob
import os
from pathlib import Path
from datetime import datetime

input_folder = './import/foo'
export_folder = './export/foo'


def merge_csvs(csv_paths: list[Path]) -> pd.DataFrame:
    """Merge bank statement CSVs (skip 4 header rows, keep valid dated rows, sort chronologically)."""
    all_dataframes = []

    for file in csv_paths:
        try:
            df = pd.read_csv(file, skiprows=4)
            if 'Tanggal / Date' in df.columns:
                clean_df = df[df['Tanggal / Date'].astype(str).str.match(r'^\d{2}/\d{2}/\d{4}', na=False)]
                all_dataframes.append(clean_df)
        except Exception as e:
            print(f"Gagal membaca {os.path.basename(file)}. Error: {e}")

    if not all_dataframes:
        return pd.DataFrame()

    merged_df = pd.concat(all_dataframes, ignore_index=True)
    merged_df['helper_date'] = pd.to_datetime(merged_df['Tanggal / Date'], format='%d/%m/%Y', errors='coerce')
    merged_df = merged_df.sort_values(by='helper_date', ascending=True)
    merged_df = merged_df.drop(columns=['helper_date'])
    merged_df = merged_df.reset_index(drop=True)
    return merged_df


def main() -> None:
    os.makedirs(export_folder, exist_ok=True)
    file_pattern = os.path.join(input_folder, '*.csv')
    csv_files = glob.glob(file_pattern)

    print(f"Ditemukan {len(csv_files)} file CSV. Memulai proses merge...")
    merged_df = merge_csvs([Path(f) for f in csv_files])

    if not merged_df.empty:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{timestamp}_Mutasi_Urut_Bersih.csv"
        output_filepath = os.path.join(export_folder, file_name)

        merged_df.to_csv(output_filepath, index=False)

        print(f"\nSukses! Data telah diurutkan dengan benar secara kronologis.")
        print(f"File disimpan sebagai: {output_filepath}")
        print(f"Total baris transaksi murni yang berhasil diamankan: {len(merged_df)} baris.")
    else:
        print("Tidak ada data yang berhasil digabungkan.")


if __name__ == "__main__":
    main()
