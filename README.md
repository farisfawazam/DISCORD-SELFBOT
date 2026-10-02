# Discord Voice Stay Manager (Terminal & VPS CLI)

> 📖 **Panduan VPS Lengkap**: Baca [VPS_GUIDE.md](VPS_GUIDE.md) untuk langkah demi langkah terminal VPS dari awal sampai jalan 24/7 background.

Selfbot Discord multi-akun berkinerja tinggi yang dirancang khusus untuk standby di Voice Channel 24/7 tanpa GUI browser, hemat resource, bebas deadcode, dan dioptimasi penuh untuk lingkungan **Terminal / SSH VPS (Linux/Ubuntu/Debian)** maupun **Android Termux**.

---

## 🎨 Tampilan & Fitur Utama

- **Custom Voice Stay Theme**: Tampilan terminal modern dengan palet khas Discord Blurple (`#5865F2`) & Voice Emerald Green (`#23A55A`), bukan tiruan mentah bot lain.
- **Account Management Dashboard**:
  - Tambah, edit, dan hapus akun secara interaktif via terminal.
  - Quick Toggle Enable / Disable per-akun.
  - Quick Toggle Audio (Mute mic & Deafen headphone).
  - Pilihan Presence Status Discord: `online`, `idle`, `dnd`, `invisible`.
- **Live Account Verifier (`python run.py --verify`)**:
  - Ping langsung ke Discord API untuk memeriksa apakah token masih aktif/valid.
  - Menampilkan Username Discord asli, server target, serta channel voice target.
- **Global Engine Settings**:
  - Pengaturan jeda waktu startup antar-akun (*stagger delay*).
  - Batas auto-reconnect saat voice disconnect.
  - Auto Termux wake-lock.
- **Pure Voice Protocol v8**:
  - Menggunakan Discord Voice Gateway v8 Heartbeat resmi (24/7 anti-zombie kick).
  - 100% bypass audio overhead / DAVE E2EE / libsodium C-compiler.
- **Headless VPS & Systemd Ready**:
  - Jalankan background tanpa prompt interaktif dengan flag `--run`.

---

## 🚀 Cara Menjalankan

### 1. Di Komputer / VPS (Linux / Windows)

```bash
# Pasang dependensi (cukup jalankan satu file ini):
python install.py
# Atau di Windows: klik ganda Install.bat

# Buka menu interaktif terminal:
python run.py
```

### 2. Menu Interaktif:

```text
 1. Start Voice Stay (24/7 Run)
 2. Account Management (Tambah, Edit, Toggle, Mute/Deaf, Presence)
 3. Verify Accounts (Live Discord API Ping Check)
 4. Global Engine Settings (Stagger Delay, Reconnect Limit)
 0. Exit
```

### 3. CLI Langsung (VPS Headless):

```bash
# Jalankan langsung semua akun aktif di background:
python run.py --run

# Verifikasi token dan akses server dari terminal:
python run.py --verify

# Tampilkan tabel konfigurasi akun:
python run.py --list
```

### 4. Background Service di VPS (Gunakan `bot.sh`)

Untuk VPS Linux, gunakan script kontrol all-in-one `bot.sh`:

```bash
chmod +x bot.sh

# Jalankan 24/7 di background (aman tutup terminal SSH):
./bot.sh start

# Cek status aktif/mati:
./bot.sh status

# Lihat log realtime:
./bot.sh log

# Hentikan bot:
./bot.sh stop
```

---

## 📁 Struktur Proyek Bersih

```
discord-selfbot/
├── run.py                 # Core Engine & Terminal UI Manager
├── accounts.json          # Database akun lokal (terlindungi .gitignore)
├── accounts.example.json  # Format contoh JSON
├── settings.json          # Konfigurasi global engine
├── requirements.txt       # Dependensi minimal (discord.py-self, aiohttp, rich, audioop-lts)
├── install.py             # Single file installer dependensi cross-platform
├── bot.sh                 # Shortcut kontrol background VPS (start/stop/status/log/menu)
├── Install.bat            # Shortcut installer Windows
├── Start.bat              # Shortcut runner Windows
├── Stop-All.bat           # Shortcut kill bot Windows
├── test_selfbot.py        # Runnable self-check test
├── ARCHITECTURE.md        # Dokumentasi teknis arsitektur
├── VPS_GUIDE.md           # Panduan lengkap setup VPS terminal dari awal
└── README.md
```
