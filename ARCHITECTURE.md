# System Architecture: Discord Voice Stay Manager

Dokumen arsitektur teknis **Discord Voice Stay Manager** versi Terminal & VPS.

---

## 1. Arsitektur Inti

### A. Bypass DAVE RTC & Media Transport
- Bot bertugas standby di Voice Channel (Mute & Deafen).
- Koneksi audio UDP (RTP/SRTP) dan enkripsi DAVE MLS E2EE tidak diperlukan.
- Menggunakan `PureVoiceStayProtocol` mewarisi `discord.VoiceProtocol`:
  - Menangkap event gateway `on_voice_state_update` dan `on_voice_server_update`.
  - Membuka WebSocket text resmi ke `wss://{endpoint}/?v=8`.
  - Mengirim Opcode 0 (Identify) dan membaca heartbeat interval dari Opcode 8 (Hello).
  - Menjalankan loop Heartbeat Opcode 3 secara berkala sesuai interval resmi Discord.
  - Server Discord memvalidasi sesi dengan Heartbeat ACK (Opcode 6) sehingga akun tidak terkena zombie kick.

### B. Pure AIOHTTP Gateway
- `discord.py-self` di-patch via `_patched_startup` dan `AsyncWsWrapper` agar menggunakan `aiohttp.ClientSession` murni tanpa ketergantungan `curl_cffi` C-binary.

### C. Terminal UI & Live Verification Engine
- Single entrypoint `run.py` menggunakan Rich terminal renderer dengan palet warna asli Discord (`#5865F2` Blurple, `#23A55A` Emerald, `#00F0FF` Cyan).
- Dilengkapi fungsi `verify_single_account` untuk mengecek validitas token, username Discord, dan akses ke target server/channel secara langsung via Discord REST API.
- Mendukung kustomisasi Presence Discord (`online`, `idle`, `dnd`, `invisible`).
- Flag `--run` untuk eksekusi headless tanpa prompt di VPS, cron, atau systemd service.

### D. Single-File Installer Engine (`install.py`)
- Self-contained bootstrap installer yang mendeteksi ketersediaan `pip` sistem (auto-install via `apt-get` / `dnf` / `ensurepip` bila belum tersedia di VPS minimal).
- Memasang dependensi dari `requirements.txt` dengan fallback otomatis PEP 668 (`--break-system-packages`) pada OS modern seperti Debian 12 / Ubuntu 24.04+.
- Verifikasi modul pasca-instalasi langsung di memori sebelum mengembalikan kode status 0.

### E. Background Daemonization & Process Controller (`bot.sh`)
- Abstraksi manajemen proses POSIX (`start`, `stop`, `restart`, `status`, `log`, `menu`).
- Isolasi proses background menggunakan `nohup ... &` dan pengalihan I/O stream ke `selfbot.log`.
- Mekanisme PID tracking via `pgrep` untuk mencegah proses ganda (*double instance*) pada akun yang sama.

### F. Keamanan & Isolasi Kredensial
- Database akun (`accounts.json`) dan log runtime diisolasi secara permanen via `.gitignore`.
- Fungsi `mask_token()` memastikan token dipotong (`abc...xyz`) saat dirender ke terminal atau tabel agar aman dari bahaya *shoulder surfing* dan *accidental screen share*.
