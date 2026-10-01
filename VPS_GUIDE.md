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

## 4. Jalankan Bot 24/7 di Background (Screen)

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

## 5. Perintah Manajemen Harian

| Kebutuhan | Perintah di Terminal VPS |
|---|---|
| Buka kembali tampilan bot | `screen -r bot` |
| Lepas layar lagi (jangan matikan) | Tekan `Ctrl + A` lalu `D` |
| Hentikan bot total | `killall python3` |
| Update kode bot ke versi terbaru | `git pull origin main` |
| Cek log bot jika via nohup | `tail -f ~/discord-selfbot/selfbot.log` |

---

## 6. Troubleshooting

- **Error `No module named pip`**:
  Jalankan `apt update && apt install -y python3-pip`, lalu ulangi `python3 install.py`.

- **Error `git pull` bertabrakan**:
  Jalankan `git stash` atau `git reset --hard origin/main`, lalu ulangi `git pull origin main`.
