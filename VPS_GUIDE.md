# Panduan Lengkap Menjalankan Discord Voice Stay di VPS

Panduan langkah demi langkah menjalankan bot di terminal VPS (Ubuntu / Debian / CentOS) agar tetap online 24/7 meskipun terminal SSH ditutup.

---

## 1. Persiapan Sistem VPS

Setelah login ke SSH VPS, jalankan update dan pasang paket yang dibutuhkan:

```bash
# Untuk Ubuntu / Debian
apt update && apt install -y git python3 python3-pip screen

# Untuk CentOS / AlmaLinux / Rocky Linux
dnf install -y git python3 python3-pip screen
```

---

## 2. Clone Repositori & Install Requirement

1. Clone repositori ke VPS:
   ```bash
   git clone https://github.com/farisfawazam/DISCORD-SELFBOT.git ~/discord-selfbot
   cd ~/discord-selfbot
   ```

2. Jalankan installer dependensi (otomatis memasang `discord.py-self`, `aiohttp`, `rich`, `audioop-lts`):
   ```bash
   python3 install.py
   ```

---

## 3. Tambah Akun Discord

Buka menu konfigurasi interaktif:

```bash
python3 run.py
```

Di dalam menu terminal:
1. Ketik `2` lalu Enter (*Account Management*).
2. Ketik `1` lalu Enter (*Tambah Akun Baru*).
3. Masukkan parameter akun:
   - **Nama Label Akun**: Nama penanda (contoh: `Akun1`).
   - **Token Discord**: Token akun Discord Anda.
   - **Server ID (Guild ID)**: ID Server tempat Voice Channel berada.
   - **Voice Channel ID**: ID Voice Channel target.
   - **Self Mute**: Ketik `y` untuk mute mic (hemat bandwidth).
   - **Self Deafen**: Ketik `y` untuk deafen headphone.
   - **Presence**: Pilih `online`, `idle`, `dnd`, atau `invisible`.
4. Tekan `0` lalu Enter untuk kembali ke Menu Utama.
5. Tekan `0` lagi lalu Enter untuk keluar ke shell VPS.

*(Data tersimpan aman di file lokal `accounts.json` dan tidak akan ter-upload ke publik).*

---

## 4. Shortcut Cepat Menjalankan Bot di VPS (1 File `bot.sh`)

Gunakan shortcut `./bot.sh` untuk kontrol praktis:

```bash
# Beri izin eksekusi sekali saja
chmod +x bot.sh

# 1. Jalankan di background 24/7 (aman close terminal SSH):
./bot.sh start

# 2. Cek status bot (apakah masih aktif/mati):
./bot.sh status

# 3. Pantau log realtime (Ctrl+C untuk keluar, bot tidak akan mati):
./bot.sh log

# 4. Hentikan bot:
./bot.sh stop

# 5. Restart bot:
./bot.sh restart

# 6. Buka menu konfigurasi akun:
./bot.sh menu
```

---

## 5. Alur Saat Login SSH VPS di Hari Berikutnya

Saat membuka terminal SSH lagi, bot di background biasanya masih tetap aktif. Cukup jalankan:

```bash
cd ~/discord-selfbot
./bot.sh status
```

- Jika `[STATUS] AKTIF`: bot masih standby 24/7 di voice channel. Untuk melihat aktivitas realtime, jalankan `./bot.sh log` (`Ctrl + C` untuk keluar).
- Jika `[STATUS] MATI` (misalnya VPS baru reboot): nyalakan kembali dengan `./bot.sh start`.

---

## 6. Aturan Penting: Buka Menu Saat Bot Sedang Running

> ⚠️ **PENTING**: Jangan memilih `1. Start Voice Stay` di menu interaktif saat bot sedang berjalan di background via `./bot.sh start`. Hal ini menyebabkan konflik *double session* pada token yang sama dan memicu auto-disconnect atau spam reconnect di Discord.

Jika ingin mengedit akun, ganti channel, atau menambah token, gunakan alur aman:

```bash
# 1. Hentikan bot background sementara
./bot.sh stop

# 2. Buka menu konfigurasi untuk edit akun/channel
./bot.sh menu

# 3. Nyalakan kembali ke background setelah selesai
./bot.sh start
```

---

## 7. Menjalankan Manual (Alternatif tanpa `./bot.sh`)

Agar bot tidak mati saat jendela terminal SSH di-close:

1. Buat sesi layar background:
   ```bash
   screen -S bot
   ```

2. Jalankan bot mode background:
   ```bash
   python3 run.py --run
   ```

3. Lepas dari sesi (*detach*):
   - Tekan kombinasi tombol keyboard: `Ctrl + A`
   - Lalu tekan tombol: `D`
   - Terminal akan menampilkan tulisan `[detached from ...]`.

Selesai. Anda aman untuk menutup (*close*) jendela terminal SSH kapan saja. Bot tetap standby di voice channel 24/7.

---

## 8. Perintah Manajemen Harian

| Kebutuhan | Perintah di Terminal VPS |
|---|---|
| Jalankan bot background | `./bot.sh start` |
| Cek bot aktif / mati | `./bot.sh status` |
| Pantau log realtime | `./bot.sh log` |
| Hentikan bot | `./bot.sh stop` |
| Restart bot | `./bot.sh restart` |
| Buka menu akun aman | `./bot.sh stop && ./bot.sh menu` |
| Update kode bot ke versi terbaru | `git pull origin main` |

---

## 9. Troubleshooting

- **Error `No module named pip`**:
  Jalankan `apt update && apt install -y python3-pip`, lalu ulangi `python3 install.py`.

- **Error `git pull` bertabrakan**:
  Jalankan `git stash` atau `git reset --hard origin/main`, lalu ulangi `git pull origin main`.
