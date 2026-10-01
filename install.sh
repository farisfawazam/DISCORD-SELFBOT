#!/bin/bash
# ==============================================================================
# DISCORD VOICE STAY - ALL-IN-ONE INSTALLER (VPS Linux & Termux)
# Jalankan: bash install.sh
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo ""
echo "============================================================"
echo "  DISCORD VOICE STAY MANAGER - INSTALLER"
echo "============================================================"
echo ""

# 1. Deteksi Lingkungan (Termux vs Linux VPS)
if [ -n "$TERMUX_VERSION" ] || [ -d "/data/data/com.termux" ]; then
    IS_TERMUX=1
    echo "[*] Terdeteksi environment: Android Termux"
else
    IS_TERMUX=0
    echo "[*] Terdeteksi environment: Linux VPS / Server"
fi

# 2. Install Sistem Package Dasar
if [ "$IS_TERMUX" -eq 1 ]; then
    echo "[*] Memperbarui package Termux..."
    pkg update -y
    pkg install -y python git
    termux-wake-lock 2>/dev/null || true

    echo "[*] Memasang dependensi Python..."
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "[*] Memperbarui package sistem VPS (apt)..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -y
        sudo apt-get install -y python3 python3-pip python3-venv git
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y python3 python3-pip git
    elif command -v yum >/dev/null 2>&1; then
        sudo yum install -y python3 python3-pip git
    fi

    # 3. Setup Virtual Environment (VENV)
    echo "[*] Menyiapkan Python Virtual Environment (venv)..."
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi

    echo "[*] Memasang dependensi Python..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt

    # 4. Setup Systemd Service Otomatis
    CURRENT_USER=$(whoami)
    SERVICE_FILE="/etc/systemd/system/discord-selfbot.service"

    echo "[*] Membuat background service systemd ($SERVICE_FILE)..."
    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Discord Voice Stay Manager 24/7
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$DIR
ExecStart=$DIR/venv/bin/python $DIR/run.py --run
Restart=always
RestartSec=10
StandardOutput=append:$DIR/selfbot.log
StandardError=append:$DIR/selfbot.log

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable discord-selfbot >/dev/null 2>&1 || true
fi

# 5. Buat Runner Shortcut (start.sh)
cat > "$DIR/start.sh" << 'EOF'
#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ -f "$DIR/venv/bin/activate" ]; then
    source "$DIR/venv/bin/activate"
fi

python3 run.py "$@"
EOF
chmod +x "$DIR/start.sh"

echo ""
echo "============================================================"
echo "  [OK] INSTALASI SELESAI 100%!"
echo "============================================================"
echo ""
echo "  Cara pakai sekarang:"
echo "  1. Buka menu terminal untuk isi token / setting akun:"
echo "     ./start.sh"
echo ""
if [ "$IS_TERMUX" -eq 0 ]; then
    echo "  2. Jalankan bot 24/7 di background VPS (systemd):"
    echo "     sudo systemctl start discord-selfbot"
    echo ""
    echo "  3. Cek status bot:"
    echo "     sudo systemctl status discord-selfbot"
    echo ""
    echo "  4. Lihat log realtime:"
    echo "     tail -f selfbot.log"
    echo ""
    echo "  Stop service:"
    echo "     sudo systemctl stop discord-selfbot"
else
    echo "  2. Jalankan bot di Termux:"
    echo "     ./start.sh --run"
fi
echo "============================================================"
echo ""
