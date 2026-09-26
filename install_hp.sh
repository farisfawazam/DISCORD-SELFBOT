#!/bin/bash
# ========================================================
# Auto-Installer Discord Voice Stay untuk HP Termux
# ========================================================
set -e

echo "=== [1/4] Menyiapkan environment di HP ==="
pkg update -y
pkg install -y proot-distro

echo "=== [2/4] Memasang runtime Linux (Debian) ==="
proot-distro install debian 2>/dev/null || true

echo "=== [3/4] Memasang discord.py-self, davey, dan flask ==="
proot-distro login debian -- bash -c "
apt update -y && apt install -y python3 python3-pip
pip3 install discord.py-self davey flask python-dotenv --break-system-packages
"

echo "=== [4/4] Verifikasi protokol DAVE di HP ==="
proot-distro login debian -- python3 -c "import davey; print('[OK] DAVE PROTOCOL BERHASIL AKTIF! Versi:', davey.DAVE_PROTOCOL_VERSION)"

# Buat shortcut eksekusi 'start' di memori HP
cat > /storage/emulated/0/discord-selfbot/start.sh << 'EOF'
#!/bin/bash
termux-wake-lock 2>/dev/null
proot-distro login debian -- python3 /storage/emulated/0/discord-selfbot/run.py
EOF
chmod +x /storage/emulated/0/discord-selfbot/start.sh

echo ""
echo "========================================================"
echo "  SUKSES 100%! Semua library termasuk DAVE sudah aktif."
echo "  Untuk menjalankan bot kapan saja di Termux, ketik:"
echo "  bash /storage/emulated/0/discord-selfbot/start.sh"
echo "========================================================"
