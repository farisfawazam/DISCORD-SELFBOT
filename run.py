import sys
import os
import site
import json
import threading
import asyncio
import logging
from datetime import datetime
import webbrowser

# Pastikan path user site-packages selalu terbaca
user_site = site.getusersitepackages()
if os.path.exists(user_site) and user_site not in sys.path:
    sys.path.insert(0, user_site)

import types

# Universal PyNaCl Mock (Solusi mutlak untuk Termux/Android & PC)
# Jika PyNaCl tidak terpasang atau gagal compile C-library, mock ini akan mengelabui
# discord.py-self sehingga bot tetap bisa connect & stay di voice tanpa crash.
try:
    import nacl.secret
    import nacl.utils
except Exception:
    nacl = types.ModuleType("nacl")
    nacl_secret = types.ModuleType("nacl.secret")
    nacl_utils = types.ModuleType("nacl.utils")

    class _DummyBox:
        NONCE_SIZE = 24
        def __init__(self, *args, **kwargs): pass
        def encrypt(self, data, *args, **kwargs):
            res = type("Res", (), {})()
            res.ciphertext = b""
            return res

    nacl_secret.SecretBox = _DummyBox
    nacl_secret.Aead = _DummyBox
    nacl_utils.random = lambda n: b"0" * n
    nacl.secret = nacl_secret
    nacl.utils = nacl_utils

    sys.modules["nacl"] = nacl
    sys.modules["nacl.secret"] = nacl_secret
    sys.modules["nacl.utils"] = nacl_utils

# Encoding fix
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from flask import Flask, jsonify, request, render_template_string
import discord
import discord.voice_client as vc
from discord.ext import commands

# Force set has_nacl agar 100% lolos verifikasi
vc.has_nacl = True

logging.getLogger("discord").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_FILE = os.path.join(BASE_DIR, "accounts.json")


def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_accounts(accs):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accs, f, indent=2, ensure_ascii=False)


# ============================================
#  State & Bot Runner
# ============================================
log_buffer = []
status_map = {}
active_runners = {}


def push_log(name, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] [{name}] {msg}"
    log_buffer.append(entry)
    if len(log_buffer) > 150:
        log_buffer.pop(0)


class BotRunner:
    def __init__(self, acc):
        self.acc = acc
        self.name = acc["name"]
        self.bot = None
        self.running = False
        self.in_voice = False
        self.reconnecting = False

    def start(self):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        self.bot = commands.Bot(
            command_prefix="!",
            self_bot=True,
            chunk_guilds_at_startup=False,
            member_cache_flags=discord.MemberCacheFlags.none(),
            max_messages=None,
            sync_presence=False,
        )
        token = self.acc["token"]

        @self.bot.event
        async def on_ready():
            if not self.running:
                await self.bot.close()
                return
            push_log(self.name, f"Login sukses sebagai {self.bot.user}")
            status_map[self.name] = {"status": "ONLINE", "detail": "Siap join voice"}

        @self.bot.event
        async def on_voice_state_update(member, before, after):
            # Hanya reconnect jika user memang sengaja dalam state in_voice
            if not self.running or not self.in_voice or self.reconnecting:
                return

            if member.id != self.bot.user.id or not (before.channel and not after.channel):
                return

            self.reconnecting = True
            push_log(self.name, "Terputus dari voice channel. Mencoba reconnect dalam 5 detik...")
            status_map[self.name] = {"status": "RECONNECTING", "detail": "Waiting 5s"}
            await asyncio.sleep(5)

            if self.running and self.in_voice:
                await self._join_voice_coro()
            self.reconnecting = False

        try:
            status_map[self.name] = {"status": "CONNECTING", "detail": "Login ke Discord..."}
            push_log(self.name, "Menghubungkan ke gateway Discord...")
            self.bot.run(token, log_handler=None)
        except Exception as e:
            push_log(self.name, f"Login gagal: {e}")
            status_map[self.name] = {"status": "ERROR", "detail": str(e)[:25]}
        finally:
            self.running = False
            self.in_voice = False
            status_map[self.name] = {"status": "OFFLINE", "detail": ""}
            push_log(self.name, "Offline.")

    def join_voice(self):
        if not self.running or not self.bot or not self.bot.loop or not self.bot.loop.is_running():
            push_log(self.name, "Bot belum login! Tunggu status ONLINE.")
            return False
        asyncio.run_coroutine_threadsafe(self._join_voice_coro(), self.bot.loop)
        return True

    async def _join_voice_coro(self):
        guild_id = int(self.acc["guild_id"])
        channel_id = int(self.acc["channel_id"])
        mute = self.acc.get("self_mute", True)
        deaf = self.acc.get("self_deaf", True)

        guild = self.bot.get_guild(guild_id)
        if not guild:
            push_log(self.name, f"ERROR: Server ID {guild_id} tidak ditemukan pada akun ini!")
            status_map[self.name] = {"status": "ERROR", "detail": "Server ID invalid"}
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            push_log(self.name, f"ERROR: Voice Channel ID {channel_id} tidak ditemukan di {guild.name}!")
            status_map[self.name] = {"status": "ERROR", "detail": "Channel ID invalid"}
            return

        status_map[self.name] = {"status": "CONNECTING", "detail": f"Join #{channel.name}..."}
        push_log(self.name, f"Menghubungkan ke #{channel.name}...")

        # Pastikan voice client lama ditutup jika ada
        for vc_item in list(self.bot.voice_clients):
            try:
                await vc_item.disconnect(force=True)
            except Exception:
                pass

        try:
            vc_client = await channel.connect(self_mute=mute, self_deaf=deaf, timeout=15.0)
            await asyncio.sleep(1.5)

            # VERIFIKASI KONEKSI
            # Tidak menggunakan guild.me karena member cache dinonaktifkan demi performa cepat
            if vc_client.is_connected() and vc_client.channel and (vc_client.channel.id == channel.id):
                try:
                    await guild.change_voice_state(channel=channel, self_mute=mute, self_deaf=deaf)
                except Exception:
                    pass
                self.in_voice = True
                m = " [Muted]" if mute else ""
                d = " [Deafened]" if deaf else ""
                push_log(self.name, f"BERHASIL masuk voice #{channel.name} @ {guild.name}{m}{d}!")
                status_map[self.name] = {"status": "VOICE", "detail": f"#{channel.name}"}
            else:
                push_log(self.name, f"Verifikasi gagal: Voice client tidak terhubung ke #{channel.name}.")
                status_map[self.name] = {"status": "ONLINE", "detail": "Gagal masuk voice"}
        except Exception as e:
            push_log(self.name, f"Gagal masuk voice: {e}")
            status_map[self.name] = {"status": "ONLINE", "detail": "Join voice error"}

    def leave_voice(self):
        if not self.bot or not self.bot.loop or not self.bot.loop.is_running():
            return
        self.in_voice = False
        push_log(self.name, "Keluar dari voice channel...")
        status_map[self.name] = {"status": "ONLINE", "detail": "Standby"}

        async def _leave():
            for vc_item in list(self.bot.voice_clients):
                try:
                    await vc_item.disconnect(force=True)
                except Exception:
                    pass
            try:
                for guild in list(self.bot.guilds):
                    await guild.change_voice_state(channel=None)
            except Exception:
                pass

        asyncio.run_coroutine_threadsafe(_leave(), self.bot.loop)

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.in_voice = False
        push_log(self.name, "Mematikan bot total...")
        status_map[self.name] = {"status": "OFFLINE", "detail": ""}

        if self.bot and self.bot.loop and self.bot.loop.is_running():
            async def _close():
                for vc_item in list(self.bot.voice_clients):
                    try:
                        await vc_item.disconnect(force=True)
                    except Exception:
                        pass
                try:
                    for guild in list(self.bot.guilds):
                        await guild.change_voice_state(channel=None)
                except Exception:
                    pass
                await self.bot.close()

            asyncio.run_coroutine_threadsafe(_close(), self.bot.loop)


# ============================================
#  Flask Web Dashboard
# ============================================
app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Discord Voice Multi-Bot</title>
  <style>
    :root {
      --bg: #0b0e14;
      --card: #151922;
      --card-border: #232936;
      --text: #e6edf3;
      --text-muted: #8b949e;
      --primary: #5865f2;
      --primary-hover: #4752c4;
      --success: #23a55a;
      --danger: #da373c;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 16px;
      min-height: 100vh;
    }
    .container { max-width: 960px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }
    .header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
    .title h1 { font-size: 20px; font-weight: 700; }
    .title p { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; }
    button {
      font-family: inherit; font-size: 13px; font-weight: 600; padding: 8px 14px;
      border-radius: 6px; border: none; cursor: pointer; transition: 0.15s;
    }
    .btn-primary { background: var(--primary); color: #fff; }
    .btn-success { background: var(--success); color: #fff; }
    .btn-danger { background: var(--danger); color: #fff; }
    .btn-dark { background: #232936; color: var(--text); }
    .card { background: var(--card); border: 1px solid var(--card-border); border-radius: 10px; overflow: hidden; padding: 16px; }
    .card-title { font-weight: 600; font-size: 14px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }
    .item { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--card-border); }
    .item:last-child { border-bottom: none; }
    .status { padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }
    .st-VOICE { background: rgba(35,165,90,0.2); color: #57f287; }
    .st-ONLINE { background: rgba(35,165,90,0.2); color: #57f287; }
    .st-CONNECTING { background: rgba(240,178,50,0.2); color: #fee75c; }
    .st-OFFLINE { background: #232936; color: #8b949e; }
    .st-ERROR { background: rgba(218,55,60,0.2); color: #ed4245; }
    .log-box { background: #07090e; border-radius: 6px; padding: 10px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 11px; height: 140px; overflow-y: auto; color: #9cdcfe; line-height: 1.4; }
    input[type=text], input[type=password] { width: 100%; box-sizing: border-box; background: #0b0e14; border: 1px solid var(--card-border); color: #fff; padding: 9px; border-radius: 6px; margin: 4px 0 10px 0; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="title">
        <h1>Discord Voice Stay Manager</h1>
        <p>Login standby otomatis. Klik tombol hijau untuk Join Voice.</p>
      </div>
      <div class="actions">
        <button class="btn-primary" onclick="toggleForm()">+ Tambah Akun</button>
        <button class="btn-success" onclick="fetch('/api/join_all',{method:'POST'}).then(load)">Join All</button>
        <button class="btn-danger" onclick="fetch('/api/leave_all',{method:'POST'}).then(load)">Leave All</button>
        <button class="btn-dark" style="color:#ff7b72; border:1px solid var(--danger);" onclick="shutdown()">Shutdown</button>
      </div>
    </div>

    <div class="card" id="form-card" style="display: none;">
      <div class="card-title">Tambah / Ubah Akun</div>
      <input type="text" id="acc-name" placeholder="Nama Akun (contoh: Akun 1)">
      <input type="password" id="acc-token" placeholder="Token Discord">
      <input type="text" id="acc-guild" placeholder="Server ID">
      <input type="text" id="acc-channel" placeholder="Voice Channel ID">
      <div style="display:flex; gap:10px;">
        <button class="btn-success" onclick="saveAccount()">Simpan</button>
        <button class="btn-dark" onclick="toggleForm()">Batal</button>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Daftar Akun</div>
      <div id="acc-list">Loading...</div>
    </div>

    <div class="card">
      <div class="card-title">
        <span>Console Log</span>
        <button class="btn-dark" style="font-size:11px; padding:4px 8px;" onclick="fetch('/api/clear_logs',{method:'POST'}).then(load)">Clear Log</button>
      </div>
      <div class="log-box" id="logs"></div>
    </div>
  </div>

  <script>
    function toggleForm() {
      const el = document.getElementById('form-card');
      el.style.display = el.style.display === 'none' ? 'block' : 'none';
    }

    async function load() {
      try {
        const res = await fetch('/api/state');
        const data = await res.json();
        const list = document.getElementById('acc-list');
        if (!data.accounts.length) {
          list.innerHTML = '<p style="color:#8b949e; text-align:center; padding:15px;">Belum ada akun. Klik tombol "+ Tambah Akun".</p>';
          return;
        }
        list.innerHTML = data.accounts.map(a => {
          const s = data.statuses[a.name] || {status: 'OFFLINE', detail: ''};
          let actionBtn = '';
          if (s.status === 'VOICE') {
            actionBtn = `<button class="btn-danger" style="padding:5px 10px; font-size:12px;" onclick="fetch('/api/voice/leave',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'${escape(a.name)}'})}).then(load)">Leave VC</button>`;
          } else if (s.status === 'ONLINE') {
            actionBtn = `<button class="btn-success" style="padding:5px 10px; font-size:12px;" onclick="fetch('/api/voice/join',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'${escape(a.name)}'})}).then(load)">Join Voice</button>`;
          } else if (s.status === 'OFFLINE' || s.status === 'ERROR') {
            actionBtn = `<button class="btn-primary" style="padding:5px 10px; font-size:12px;" onclick="fetch('/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'${escape(a.name)}'})}).then(load)">Login</button>`;
          } else {
            actionBtn = `<button class="btn-dark" style="padding:5px 10px; font-size:12px;" disabled>...</button>`;
          }

          return `
            <div class="item">
              <div>
                <strong>${escape(a.name)}</strong><br>
                <span class="status st-${s.status}">${s.status}</span>
                <small style="color:#8b949e; margin-left:6px;">${escape(s.detail)}</small>
              </div>
              <div style="display:flex; gap:6px;">
                ${actionBtn}
                <button class="btn-dark" style="padding:5px 8px; font-size:12px; color:#ff7b72;" onclick="del('${escape(a.name)}')">&times;</button>
              </div>
            </div>
          `;
        }).join('');

        const logEl = document.getElementById('logs');
        logEl.innerHTML = data.logs.map(l => `<div>${escape(l)}</div>`).join('');
        logEl.scrollTop = logEl.scrollHeight;
      } catch (e) {}
    }

    async function saveAccount() {
      const name = document.getElementById('acc-name').value.trim();
      const token = document.getElementById('acc-token').value.trim();
      const guild = document.getElementById('acc-guild').value.trim();
      const channel = document.getElementById('acc-channel').value.trim();
      if (!name || !token || !guild || !channel) { alert("Semua kolom harus diisi!"); return; }

      await fetch('/api/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, token, guild_id: guild, channel_id: channel, self_mute: true, self_deaf: true})
      });
      toggleForm();
      load();
    }

    async function del(name) {
      if (!confirm('Hapus akun ' + name + '?')) return;
      await fetch('/api/delete', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name})
      });
      load();
    }

    async function shutdown() {
      if (!confirm("Matikan server dan semua bot?")) return;
      await fetch('/api/shutdown', {method:'POST'});
      document.body.innerHTML = '<div style="text-align:center; padding:50px; color:#8b949e;"><h2>Server telah dimatikan.</h2><p>Tab ini bisa ditutup.</p></div>';
    }

    function escape(s) {
      return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    load();
    setInterval(load, 2000);
  </script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/state")
def api_state():
    return jsonify({"accounts": load_accounts(), "statuses": status_map, "logs": log_buffer})


@app.route("/api/voice/join", methods=["POST"])
def api_voice_join():
    name = request.json.get("name")
    if name in active_runners:
        active_runners[name].join_voice()
    return jsonify({"ok": True})


@app.route("/api/voice/leave", methods=["POST"])
def api_voice_leave():
    name = request.json.get("name")
    if name in active_runners:
        active_runners[name].leave_voice()
    return jsonify({"ok": True})


@app.route("/api/join_all", methods=["POST"])
def api_join_all():
    for runner in active_runners.values():
        if runner.running:
            runner.join_voice()
    return jsonify({"ok": True})


@app.route("/api/leave_all", methods=["POST"])
def api_leave_all():
    for runner in active_runners.values():
        if runner.running:
            runner.leave_voice()
    return jsonify({"ok": True})


@app.route("/api/start", methods=["POST"])
def api_start():
    name = request.json.get("name")
    acc = next((a for a in load_accounts() if a["name"] == name), None)
    if acc and (name not in active_runners or not active_runners[name].running):
        r = BotRunner(acc)
        active_runners[name] = r
        r.start()
    return jsonify({"ok": True})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    name = request.json.get("name")
    if name in active_runners:
        active_runners[name].stop()
        status_map[name] = {"status": "OFFLINE", "detail": ""}
    return jsonify({"ok": True})


@app.route("/api/start_all", methods=["POST"])
def api_start_all():
    for acc in load_accounts():
        name = acc["name"]
        if name not in active_runners or not active_runners[name].running:
            r = BotRunner(acc)
            active_runners[name] = r
            r.start()
    return jsonify({"ok": True})


@app.route("/api/stop_all", methods=["POST"])
def api_stop_all():
    for r in active_runners.values():
        r.stop()
    for a in load_accounts():
        status_map[a["name"]] = {"status": "OFFLINE", "detail": ""}
    return jsonify({"ok": True})


@app.route("/api/save", methods=["POST"])
def api_save():
    d = request.json
    accs = [a for a in load_accounts() if a["name"] != d["name"]]
    accs.append(d)
    save_accounts(accs)
    return jsonify({"ok": True})


@app.route("/api/delete", methods=["POST"])
def api_delete():
    name = request.json.get("name")
    if name in active_runners:
        active_runners[name].stop()
    save_accounts([a for a in load_accounts() if a["name"] != name])
    if name in status_map:
        del status_map[name]
    return jsonify({"ok": True})


@app.route("/api/clear_logs", methods=["POST"])
def api_clear_logs():
    global log_buffer
    log_buffer = []
    return jsonify({"ok": True})


@app.route("/api/shutdown", methods=["POST"])
def api_shutdown():
    for r in active_runners.values():
        r.stop()
    def _exit():
        import time
        time.sleep(1)
        os._exit(0)
    threading.Thread(target=_exit, daemon=True).start()
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = 5050
    print("=" * 45)
    print("  Discord Voice Stay Multi-Bot (Single File)")
    print(f"  Buka di Browser: http://localhost:{port}")
    print("=" * 45)

    # Auto connect semua akun saat pertama kali run
    for acc in load_accounts():
        runner = BotRunner(acc)
        active_runners[acc["name"]] = runner
        runner.start()

    # Buka browser otomatis jika dijalankan di desktop
    if sys.platform == "win32":
        threading.Thread(target=lambda: (asyncio.run(asyncio.sleep(1.5)), webbrowser.open(f"http://localhost:{port}")), daemon=True).start()

    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
