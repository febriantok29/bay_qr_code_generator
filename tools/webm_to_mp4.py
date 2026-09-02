import os
import subprocess
from pathlib import Path
from datetime import datetime

def convert_webm_to_mp4(input_file: Path, output_file: Path) -> bool:
    try:
        command = [
            'ffmpeg', '-i', str(input_file), '-c:v', 'libx264', '-preset', 'medium',
            '-crf', '23', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart',
            '-y', str(output_file)
        ]
        
        print(f"Mengkonversi: {input_file.name} → {output_file.name}")
        
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode == 0:
            print(f"✓ Sukses: {output_file.name}")
            return True
        else:
            print(f"✗ Gagal: {input_file.name}")
            print(f"Error: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("Error: FFmpeg tidak ditemukan. Silakan install FFmpeg terlebih dahulu.")
        print("Install dengan: brew install ffmpeg (macOS)")
        return False
    except Exception as e:
        print(f"Error mengkonversi {input_file.name}: {e}")
        return False

def batch_convert_webm_to_mp4():
    script_dir = Path(__file__).parent.parent
    import_dir = script_dir / 'import' / 'webm-to-mp4'
    
    today = datetime.now().strftime('%Y-%m-%d')
    export_dir = script_dir / 'export' / 'webm-to-mp4' / today
    
    export_dir.mkdir(parents=True, exist_ok=True)
    
    webm_files = list(import_dir.glob('*.webm'))
    
    if not webm_files:
        print(f"Tidak ada file .webm ditemukan di {import_dir}")
        return
    
    print(f"Ditemukan {len(webm_files)} file .webm untuk dikonversi\n")
    
    success_count = 0
    failed_count = 0
    
    for webm_file in webm_files:
        output_file = export_dir / f"{webm_file.stem}.mp4"
        
        if convert_webm_to_mp4(webm_file, output_file):
            success_count += 1
        else:
            failed_count += 1
        print()
    
    print("=" * 50)
    print("Konversi selesai!")
    print(f"✓ Berhasil: {success_count}")
    print(f"✗ Gagal: {failed_count}")
    print(f"Folder output: {export_dir}")
    print("=" * 50)

if __name__ == "__main__":
    batch_convert_webm_to_mp4()
