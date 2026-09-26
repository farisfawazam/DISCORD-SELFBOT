#!/bin/bash
# ========================================================
# Discord Voice Stay - Installer (Gaya NeuraSelf)
# ========================================================
set -e

echo "=========================================="
echo "  [1/3] Memperbarui Packages Termux..."
echo "=========================================="
pkg update -y
pkg install -y python git clang make libffi

echo "=========================================="
echo "  [2/3] Memasang Library (Metode NeuraSelf)..."
echo "=========================================="
pip install --upgrade pip setuptools wheel
pip install flask python-dotenv rich

# Install commit discord.py-self yang teruji stabil di Termux (sama persis dengan NeuraSelf)
echo "Menginstall discord.py-self engine..."
pip install git+https://github.com/dolfies/discord.py-self@20ae80b398ec83fa272f0a96812140e14868c88 --force-reinstall --no-cache-dir

echo "=========================================="
echo "  [3/3] Selesai!"
echo "=========================================="
echo "Semua dependensi terpasang 100% tanpa error compile."
echo "Untuk menjalankan, ketik:"
echo "cd /storage/emulated/0/discord-selfbot && python run.py"
echo "=========================================="
