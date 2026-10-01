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
- Flag `--run` untuk eksekusi tanpa prompt di VPS / systemd service.
