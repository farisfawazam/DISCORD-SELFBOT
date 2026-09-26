#!/bin/bash
# ================================================
# Discord Selfbot - Oracle Cloud VPS Setup Script
# Jalankan sekali setelah SSH ke VPS
# ================================================
set -e

echo "=== [1/5] Update system ==="
sudo apt update && sudo apt upgrade -y

echo "=== [2/5] Install Python 3.10+ ==="
sudo apt install -y python3 python3-pip python3-venv git

echo "=== [3/5] Setup project ==="
mkdir -p ~/discord-selfbot
cd ~/discord-selfbot

# Buat virtual environment
python3 -m venv venv
source venv/bin/activate

echo "=== [4/5] Install dependencies ==="
pip install --upgrade pip
pip install discord.py-self PyNaCl davey python-dotenv

echo "=== [5/5] Setup systemd service ==="
sudo tee /etc/systemd/system/discord-selfbot.service > /dev/null <<EOF
[Unit]
Description=Discord Selfbot - Stay Voice Channel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/discord-selfbot
ExecStart=$HOME/discord-selfbot/venv/bin/python stay_vc.py
Restart=always
RestartSec=10
StandardOutput=append:$HOME/discord-selfbot/selfbot.log
StandardError=append:$HOME/discord-selfbot/selfbot.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable discord-selfbot

echo ""
echo "============================================"
echo "  Setup selesai!"
echo "============================================"
echo ""
echo "  Langkah selanjutnya:"
echo "  1. Edit file .env:"
echo "     nano ~/discord-selfbot/.env"
echo ""
echo "  2. Upload file stay_vc.py dan config.py"
echo "     (atau copy paste isinya)"
echo ""
echo "  3. Start service:"
echo "     sudo systemctl start discord-selfbot"
echo ""
echo "  4. Cek status:"
echo "     sudo systemctl status discord-selfbot"
echo ""
echo "  5. Lihat log:"
echo "     tail -f ~/discord-selfbot/selfbot.log"
echo ""
echo "  Stop service:"
echo "     sudo systemctl stop discord-selfbot"
echo "============================================"
