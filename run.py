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
        self.loop = None
        self.running = False

    def start(self):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.bot = commands.Bot(
            command_prefix="!",
            self_bot=True,
            chunk_guilds_at_startup=False,
            member_cache_flags=discord.MemberCacheFlags.none(),
            max_messages=None,
            sync_presence=False,
        )
        token = self.acc["token"]
        guild_id = int(self.acc["guild_id"])
        channel_id = int(self.acc["channel_id"])
        mute = self.acc.get("self_mute", True)
        deaf = self.acc.get("self_deaf", True)
        rc = 0

        @self.bot.event
        async def on_ready():
            nonlocal rc
            if not self.running:
                await self.bot.close()
                return

            push_log(self.name, f"Login as {self.bot.user}")
            status_map[self.name] = {"status": "ONLINE", "detail": str(self.bot.user)}
            g = self.bot.get_guild(guild_id)
            ch = g.get_channel(channel_id) if g else None
            if not ch:
                push_log(self.name, "Error: Channel tidak ditemukan!")
                status_map[self.name] = {"status": "ERROR", "detail": "Channel not found"}
                await self.bot.close()
                return

            try:
                await ch.connect(self_mute=mute, self_deaf=deaf)
                await asyncio.sleep(1)
                try:
                    await g.change_voice_state(channel=ch, self_mute=mute, self_deaf=deaf)
                except Exception:
                    pass
                m = " [Muted]" if mute else ""
                d = " [Deafened]" if deaf else ""
                push_log(self.name, f"Connected to #{ch.name} @ {g.name}{m}{d}")
                status_map[self.name] = {"status": "VOICE", "detail": f"#{ch.name}"}
                rc = 0
            except Exception as e:
                push_log(self.name, f"Connect error: {e}")
                status_map[self.name] = {"status": "ERROR", "detail": str(e)[:25]}
                await self.bot.close()

        @self.bot.event
        async def on_voice_state_update(member, before, after):
            nonlocal rc
            # Jika bot sengaja dimatikan, jangan reconnect sama sekali
            if not self.running:
                return

            if member.id != self.bot.user.id or not (before.channel and not after.channel):
                return

            rc += 1
            if rc > 10:
                push_log(self.name, "Max reconnect reached. Stopped.")
                status_map[self.name] = {"status": "ERROR", "detail": "Max reconnect"}
                await self.bot.close()
                return

            delay = min(5 * rc, 60)
            push_log(self.name, f"DC. Reconnecting in {delay}s...")
            status_map[self.name] = {"status": "RECONNECTING", "detail": f"{delay}s"}
            await asyncio.sleep(delay)

            if not self.running:
                return

            g = self.bot.get_guild(guild_id)
            ch = g.get_channel(channel_id) if g else None
            if ch and self.running:
                try:
                    await ch.connect(self_mute=mute, self_deaf=deaf)
                    await asyncio.sleep(1)
                    await g.change_voice_state(channel=ch, self_mute=mute, self_deaf=deaf)
                    push_log(self.name, "Reconnected!")
                    status_map[self.name] = {"status": "VOICE", "detail": f"#{ch.name}"}
                    rc = 0
                except Exception as e:
                    push_log(self.name, f"Reconnect failed: {e}")

        try:
            status_map[self.name] = {"status": "CONNECTING", "detail": "Starting..."}
            push_log(self.name, "Connecting to gateway...")
            self.bot.run(token, log_handler=None)
        except Exception as e:
            push_log(self.name, f"Fatal: {e}")
            status_map[self.name] = {"status": "ERROR", "detail": str(e)[:25]}
        finally:
            self.running = False
            status_map[self.name] = {"status": "OFFLINE", "detail": ""}
            push_log(self.name, "Stopped.")

    def stop(self):
        if not self.running:
            return
        self.running = False
        push_log(self.name, "Stopping and disconnecting...")
        status_map[self.name] = {"status": "OFFLINE", "detail": ""}

        if self.bot and self.loop and self.loop.is_running():
            async def _close():
                # 1. Keluar dari voice channel secara resmi
                for vc in list(self.bot.voice_clients):
                    try:
                        await vc.disconnect(force=True)
                    except Exception:
                        pass
                # 2. Update status gateway voice state ke None
                try:
                    for guild in list(self.bot.guilds):
                        await guild.change_voice_state(channel=None)
                except Exception:
                    pass
                # 3. Putus session bot Discord total
                await self.bot.close()

            asyncio.run_coroutine_threadsafe(_close(), self.loop)


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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
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
      font-family: 'Inter', sans-serif;
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
    .log-box { background: #07090e; border-radius: 6px; padding: 12px; font-family: 'JetBrains Mono', monospace; font-size: 11px; height: 160px; overflow-y: auto; color: #9cdcfe; line-height: 1.5; }
    input[type=text], input[type=password] { width: 100%; box-sizing: border-box; background: #0b0e14; border: 1px solid var(--card-border); color: #fff; padding: 9px; border-radius: 6px; margin: 4px 0 10px 0; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="title">
        <h1>Discord Voice Stay Manager</h1>
        <p>Stay 24/7 in Discord Voice Channel</p>
      </div>
      <div class="actions">
        <button class="btn-primary" onclick="toggleForm()">+ Tambah Akun</button>
        <button class="btn-success" onclick="fetch('/api/start_all',{method:'POST'}).then(load)">Start All</button>
        <button class="btn-danger" onclick="fetch('/api/stop_all',{method:'POST'}).then(load)">Stop All</button>
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
          const isRun = ['VOICE', 'ONLINE', 'CONNECTING', 'RECONNECTING'].includes(s.status);
          return `
            <div class="item">
              <div>
                <strong>${escape(a.name)}</strong><br>
                <span class="status st-${s.status}">${s.status}</span>
                <small style="color:#8b949e; margin-left:6px;">${escape(s.detail)}</small>
              </div>
              <div style="display:flex; gap:6px;">
                ${isRun 
                  ? `<button class="btn-danger" style="padding:5px 10px; font-size:12px;" onclick="fetch('/api/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'${escape(a.name)}'})}).then(load)">Stop</button>`
                  : `<button class="btn-success" style="padding:5px 10px; font-size:12px;" onclick="fetch('/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'${escape(a.name)}'})}).then(load)">Start</button>`
                }
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

    app.run(host="0.0.0.0", port=port, debug=False)
