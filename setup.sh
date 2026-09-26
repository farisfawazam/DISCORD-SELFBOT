#!/data/data/com.termux/files/usr/bin/bash
# ========================================================
# Setup 1x Discord Voice Stay (Auto-Install Prebuilt Davey for Termux Python 3.14)
# ========================================================
set -e

echo "=========================================="
echo "  [1/3] Menyiapkan Python & Pip Termux..."
echo "=========================================="
pkg update -y
pkg install -y python python-pip git clang make libffi

# Sinkronkan pip dengan versi Python saat ini
python -m ensurepip --upgrade 2>/dev/null || true
python -m pip install --upgrade pip setuptools wheel
python -m pip install flask python-dotenv discord.py-self==2.1.0

echo "=========================================="
echo "  [2/3] Memasang Pre-built Binary Davey (Tanpa Compile Rust)..."
echo "=========================================="

SITE_DIR=$(python -c "import site; print(site.getsitepackages()[0])")
echo "Lokasi site-packages: $SITE_DIR"

# Download wheel biner Python 3.14 aarch64 langsung dari PyPI
WHEEL_URL="https://files.pythonhosted.org/packages/21/de/91f95b4b673163fe691f21cdc3b50577fb8bda687e5f7b53ab237f94a860/davey-0.1.6-cp314-cp314-manylinux_2_17_aarch64.manylinux2014_aarch64.whl"

python -c "
import urllib.request, zipfile, io, sys

url = '$WHEEL_URL'
site_dir = '$SITE_DIR'
print('Mengunduh prebuilt davey binary untuk Python 3.14 ARM64...')
data = urllib.request.urlopen(url).read()
print(f'Mengekstrak binary ({len(data)} bytes) ke ' + site_dir + '...')
z = zipfile.ZipFile(io.BytesIO(data))
z.extractall(site_dir)
print('[OK] Binary davey berhasil diekstrak!')
"

echo "=========================================="
echo "  [3/3] Memverifikasi Instalasi Davey..."
echo "=========================================="
python -c "import davey; print('  [SUKSES] Davey Protocol Version:', davey.DAVE_PROTOCOL_VERSION)"

echo ""
echo "=========================================="
echo "  SETUP 1X SELESAI & BERHASIL 100%!"
echo "  Sekarang kamu tinggal ketik:"
echo "  python run.py"
echo "=========================================="
