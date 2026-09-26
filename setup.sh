#!/data/data/com.termux/files/usr/bin/bash
# ========================================================
# Setup 1x Discord Voice Stay (Self-Healing Pip & Auto-Extract)
# ========================================================
set -e

echo "=========================================="
echo "  [1/4] Memeriksa & Memperbaiki Pip Termux..."
echo "=========================================="
# Jika pip rusak (akibat transisi python 3.13 ke 3.14), bersihkan dan pasang ulang otomatis
if ! python3 -m pip --version >/dev/null 2>&1; then
    echo "[!] Mendeteksi pip corrupt. Memperbaiki secara otomatis..."
    rm -rf /data/data/com.termux/files/usr/lib/python*/site-packages/pip* 2>/dev/null || true
    rm -rf /data/data/com.termux/files/usr/lib/python*/site-packages/setuptools* 2>/dev/null || true
    rm -rf /data/data/com.termux/files/usr/lib/python*/site-packages/wheel* 2>/dev/null || true
    pkg update -y
    pkg install --reinstall -y python python-pip
fi

echo "=========================================="
echo "  [2/4] Menginstall Package Dasar..."
echo "=========================================="
pkg install -y git clang make libffi

echo "=========================================="
echo "  [3/4] Menginstall Library Python..."
echo "=========================================="
python3 -m pip install flask python-dotenv discord.py-self==2.1.0

echo "=========================================="
echo "  [4/4] Memasang Pre-built Binary Davey (DAVE Protocol)..."
echo "=========================================="
SITE_DIR=$(python3 -c "import site; print(site.getsitepackages()[0])")

python3 -c "
import urllib.request, zipfile, io, sys

# Mendeteksi versi minor python di Termux (misal 3.14 -> 314, 3.13 -> 313)
v = f'{sys.version_info.major}{sys.version_info.minor}'
urls = {
    '314': 'https://files.pythonhosted.org/packages/21/de/91f95b4b673163fe691f21cdc3b50577fb8bda687e5f7b53ab237f94a860/davey-0.1.6-cp314-cp314-manylinux_2_17_aarch64.manylinux2014_aarch64.whl',
    '313': 'https://files.pythonhosted.org/packages/c0/50/fd017a3f89252597e0c85a4552fe732add13c167f07059886f8f9add218b/davey-0.1.6-cp313-cp313-manylinux_2_17_aarch64.manylinux2014_aarch64.whl',
    '312': 'https://files.pythonhosted.org/packages/72/c0/51b69f42e2b1a873ed279af0f581eab91744919dc41c006eb20ce603e567/davey-0.1.6-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl'
}

url = urls.get(v, urls['314'])
print(f'Mengunduh prebuilt davey binary untuk Python {v} aarch64...')
try:
    data = urllib.request.urlopen(url).read()
    print(f'Mengekstrak {len(data)} bytes ke $SITE_DIR...')
    z = zipfile.ZipFile(io.BytesIO(data))
    z.extractall('$SITE_DIR')
    print('[OK] Binary davey berhasil terpasang!')
except Exception as e:
    print('[WARN] Gagal auto-extract:', e)
"

python3 -c "import davey; print('  [SUKSES] Davey Protocol Version:', davey.DAVE_PROTOCOL_VERSION)" 2>/dev/null || echo "[!] Lanjut menjalankan bot..."

echo ""
echo "=========================================="
echo "  SETUP SELESAI!"
echo "  Tinggal ketik:"
echo "  python run.py"
echo "=========================================="
