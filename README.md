# Discord Voice Stay Multi-Bot (Web GUI & 24/7 Stay)

Aplikasi selfbot Discord ringan untuk standby di voice channel 24/7 tanpa perlu membuka client Discord. Mendukung multi-akun, Web GUI localhost, auto mute & deafen, serta auto-reconnect.

---

## 📱 Cara Install di Termux (HP Android)

1. Buka Termux, jalankan perintah berikut:
```bash
pkg update -y && pkg install python git -y
git clone https://github.com/USERNAME/REPO_NAME.git ~/selfbot
cd ~/selfbot
pip install -r requirements.txt
```

2. Jalankan bot:
```bash
python run.py
```
*(Atau di background: `termux-wake-lock && nohup python run.py > /dev/null 2>&1 &`)*

3. Buka browser HP (Chrome) ke:
👉 **`http://localhost:5050`**
Lo bisa langsung input token, server ID, dan channel ID dari web dashboard di HP!

---

## 💻 Cara Install di PC (Windows)

1. Download repo ini atau `git clone`.
2. Klik 2x file: **`Start.bat`** (atau jalankan `python run.py`).
3. Browser otomatis terbuka ke **`http://localhost:5050`**.

---

## ⚙️ Fitur
- **Web Dashboard Localhost:** Interface modern dan ringan untuk manage banyak akun sekaligus.
- **Multi-Account:** Tambah akun sebanyak-banyaknya.
- **Mute & Deafen Otomatis:** Ikon mic dicoret dan headphone merah otomatis aktif di Discord.
- **Auto Reconnect:** Otomatis menyambung kembali jika internet putus.
- **Silent & Ringan:** Tanpa membuka aplikasi Discord resmi, hemat baterai dan RAM.
