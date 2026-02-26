import qrcode
from PIL import Image
import os
from datetime import datetime
import subprocess
from pathlib import Path

def create_export_folder():
    """Create export folder if it doesn't exist"""
    if not os.path.exists("export"):
        os.makedirs("export")
        print("✓ Folder 'export' dibuat")

def get_user_input():
    """Get text input from user"""
    print("\n" + "="*50)
    print("📱 QR CODE GENERATOR")
    print("="*50)
    text = input("\nMasukkan teks/URL yang ingin di-encode: ").strip()
    
    if not text:
        print("❌ Teks tidak boleh kosong!")
        return get_user_input()
    
    return text

def ask_for_logo():
    """Ask if user wants to add a logo"""
    while True:
        choice = input("\nTambahkan gambar/logo di tengah QR code? (y/n): ").strip().lower()
        if choice in ['y', 'n']:
            return choice == 'y'
        print("❌ Input tidak valid. Gunakan 'y' atau 'n'")

def get_logo_path():
    """Get logo path from user using native macOS file picker"""
    try:
        # AppleScript untuk membuka native file picker di macOS
        script = '''
        tell application "System Events"
            activate
            set selectedFiles to choose file with prompt "Pilih gambar/logo (PNG, JPG, SVG, dll):" of type {"public.image", "public.svg-image"}
            return POSIX path of selectedFiles
        end tell
        '''
        
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0 and result.stdout.strip():
            file_path = result.stdout.strip()
            return file_path
        else:
            print("❌ Tidak ada file yang dipilih. Membatalkan...")
            return None
            
    except Exception as e:
        print(f"❌ Error membuka file picker: {e}")
        print("Silakan masukkan path secara manual:")
        return input("Path ke gambar: ").strip() or None

def ask_logo_color():
    """Ask if logo should be color or black & white"""
    while True:
        choice = input("Tampilkan logo dalam warna? (y/n): ").strip().lower()
        if choice in ['y', 'n']:
            return choice == 'y'
        print("❌ Input tidak valid. Gunakan 'y' atau 'n'")

def convert_svg_to_png(svg_path):
    """Convert SVG file to PNG using available tools"""
    png_path = os.path.join(os.path.dirname(svg_path), f"_temp_{int(datetime.now().timestamp())}.png")
    
    # Try method 1: ImageMagick (convert command)
    try:
        result = subprocess.run(
            ['convert', svg_path, png_path],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        if result.returncode == 0 and os.path.exists(png_path):
            print(f"✓ SVG dikonversi ke PNG (ImageMagick)")
            return png_path
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠️ ImageMagick gagal: {e}")
    
    # Try method 2: sips (built-in macOS)
    try:
        result = subprocess.run(
            ['sips', '-s', 'format', 'png', svg_path, '--out', png_path],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        if result.returncode == 0 and os.path.exists(png_path):
            print(f"✓ SVG dikonversi ke PNG (sips)")
            return png_path
    except Exception as e:
        print(f"⚠️ sips gagal: {e}")
    
    # Try method 3: cairosvg (if installed)
    try:
        import cairosvg
        cairosvg.svg2png(url=svg_path, write_to=png_path)
        if os.path.exists(png_path):
            print(f"✓ SVG dikonversi ke PNG (cairosvg)")
            return png_path
    except ImportError:
        pass
    except Exception as e:
        print(f"⚠️ cairosvg gagal: {e}")
    
    # Semua metode gagal
    print("❌ Tidak bisa konversi SVG. Instalasi ImageMagick dengan Homebrew:")
    print("   brew install imagemagick")
    print("\n   Atau instalasi cairosvg (memerlukan system libraries):")
    print("   pip3 install cairosvg")
    return None

def add_logo_to_qr(qr_img, logo_path, color_mode=True):
    """Add logo/image to center of QR code"""
    try:
        # Check if logo is SVG and convert if needed
        if logo_path.lower().endswith('.svg'):
            print("🔄 Mengkonversi SVG ke PNG...")
            converted_path = convert_svg_to_png(logo_path)
            if not converted_path:
                return qr_img
            logo_path = converted_path
        
        logo = Image.open(logo_path)
        
        # Convert to RGBA if it has alpha channel, otherwise convert to RGB
        if logo.mode != 'RGBA':
            logo = logo.convert('RGBA')
        
        # Apply color mode filter if needed
        if not color_mode:
            rgb_version = logo.convert('RGB')
            gray_version = rgb_version.convert('L')
            # Convert back to RGBA to preserve transparency
            alpha_channel = logo.split()[3] if len(logo.split()) == 4 else Image.new('L', logo.size, 255)
            logo = Image.merge('RGBA', (gray_version, gray_version, gray_version, alpha_channel))
        
        # Calculate logo size (1/3 of QR code for better visibility)
        qr_width, qr_height = qr_img.size
        logo_size = min(qr_width, qr_height) // 3
        
        # Resize logo
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        
        # Convert QR code to RGBA
        qr_rgba = qr_img.convert('RGBA')
        
        # Calculate position for logo at center
        pos_x = (qr_width - logo_size) // 2
        pos_y = (qr_height - logo_size) // 2
        
        # Paste logo with alpha transparency (transparent background preserved)
        qr_rgba.paste(logo, (pos_x, pos_y), logo)
        
        # Convert back to RGB for final output
        qr_final = Image.new('RGB', qr_rgba.size, 'white')
        qr_final.paste(qr_rgba, mask=qr_rgba.split()[3])
        
        print(f"✓ Logo ditambahkan (ukuran: 1/3 QR code)")
        
        # Clean up temporary PNG if it was converted from SVG
        if logo_path.startswith('_temp_'):
            try:
                os.remove(logo_path)
            except:
                pass
        
        return qr_final
    except Exception as e:
        print(f"❌ Error menambahkan logo: {e}")
        return qr_img

def get_output_filename():
    """Get output filename from user"""
    custom_name = input("\nNama file khusus? (kosongkan untuk hanya timestamp): ").strip()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if custom_name:
        # Remove .png extension if user added it
        if custom_name.lower().endswith('.png'):
            custom_name = custom_name[:-4]
        filename = f"{timestamp}_{custom_name}.png"
    else:
        filename = f"{timestamp}.png"
    
    return filename

def main():
    create_export_folder()
    
    # Get text from user
    text = get_user_input()
    
    # Create QR code instance
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # Higher error correction for logo
        box_size=10,
        border=4,
    )
    
    # Add data to QR code
    qr.add_data(text)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    
    # Ask about logo
    if ask_for_logo():
        logo_path = get_logo_path()
        if logo_path:  # Check if user didn't cancel the file picker
            color_option = ask_logo_color()
            img = add_logo_to_qr(img, logo_path, color_option)
        else:
            print("⚠️ Logo diabaikan, melanjutkan tanpa logo...")
    
    # Get output filename
    filename = get_output_filename()
    output_path = os.path.join("export", filename)
    
    # Save the QR code
    img.save(output_path)
    
    print(f"\n✓ QR code berhasil dibuat!")
    print(f"📁 Disimpan di: {output_path}")
    print(f"📝 Teks yang di-encode: {text}")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
