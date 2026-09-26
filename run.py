import sys
import os
import site
import time
import json
import threading
import asyncio
import logging
from datetime import datetime
import webbrowser
import types

# Pastikan path user site-packages terbaca
user_site = site.getusersitepackages()
if os.path.exists(user_site) and user_site not in sys.path:
    sys.path.insert(0, user_site)

# Mock PyNaCl in-memory (karena stay di voice tanpa kirim audio tidak butuh libsodium C)
if "nacl" not in sys.modules:
    nacl = types.ModuleType("nacl")
    nacl_secret = types.ModuleType("nacl.secret")
    nacl_utils = types.ModuleType("nacl.utils")

    class _DummyBox:
        NONCE_SIZE = 24
        def __init__(self, *args, **kwargs): pass
        def encrypt(self, data, *args, **kwargs):
            r = type("R", (), {})()
            r.ciphertext = b""
            return r

    nacl_secret.SecretBox = _DummyBox
    nacl_secret.Aead = _DummyBox
    nacl_utils.random = lambda n: b"0" * n
    nacl.secret = nacl_secret
    nacl.utils = nacl_utils
    sys.modules["nacl"] = nacl
    sys.modules["nacl.secret"] = nacl_secret
    sys.modules["nacl.utils"] = nacl_utils

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

vc.has_nacl = True

logging.getLogger("discord").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

# Auto detect direktori kerja (HP /storage/emulated/0/discord-selfbot atau PC)
CANDIDATE_DIRS = [
    "/storage/emulated/0/discord-selfbot",
    os.path.dirname(os.path.abspath(__file__)),
    os.path.expanduser("~/selfbot"),
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
for d in CANDIDATE_DIRS:
    if os.path.exists(d):
        BASE_DIR = d
        break

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
#  Global Shared State & Core Bot Client
# ============================================
log_buffer = []
status_map = {}
bots = {}
main_loop = None


def push_log(name, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] [{name}] {msg}"
    log_buffer.append(entry)
    print(entry)
    if len(log_buffer) > 150:
        log_buffer.pop(0)


class BotClient(commands.Bot):
    def __init__(self, acc):
        self.acc = acc
        self.account_name = acc["name"]
        self.token = acc["token"]
        self.guild_id = int(acc["guild_id"])
        self.channel_id = int(acc["channel_id"])
        self.self_mute = acc.get("self_mute", True)
        self.self_deaf = acc.get("self_deaf", True)
        self.in_voice = False
        self.is_reconnecting = False
        self.is_active = True

        super().__init__(
            command_prefix="!",
            self_bot=True,
            chunk_guilds_at_startup=False,
            member_cache_flags=discord.MemberCacheFlags.none(),
            max_messages=None,
            sync_presence=False,
        )

    async def on_ready(self):
        push_log(self.account_name, f"Login sukses sebagai {self.user}")
        status_map[self.account_name] = {"status": "ONLINE", "detail": "Siap join voice"}

    async def on_voice_state_update(self, member, before, after):
        if not self.is_active or not self.in_voice or self.is_reconnecting:
            return

        if member.id != self.user.id or not (before.channel and not after.channel):
            return

        self.is_reconnecting = True
        push_log(self.account_name, "Koneksi voice drop. Reconnecting dalam 5 detik...")
        status_map[self.account_name] = {"status": "RECONNECTING", "detail": "Waiting 5s"}
        await asyncio.sleep(5)

        if self.is_active and self.in_voice:
            await self.action_join_voice()
        self.is_reconnecting = False

    async def action_join_voice(self):
        guild = self.get_guild(self.guild_id)
        if not guild:
            push_log(self.account_name, f"ERROR: Server ID {self.guild_id} tidak ditemukan!")
            status_map[self.account_name] = {"status": "ERROR", "detail": "Server ID invalid"}
            return False

        channel = guild.get_channel(self.channel_id)
        if not channel:
            push_log(self.account_name, f"ERROR: Voice Channel ID {self.channel_id} tidak ditemukan di {guild.name}!")
            status_map[self.account_name] = {"status": "ERROR", "detail": "Channel ID invalid"}
            return False

        status_map[self.account_name] = {"status": "CONNECTING", "detail": f"Join #{channel.name}..."}
        push_log(self.account_name, f"Menghubungkan ke #{channel.name}...")

        for vc_item in list(self.voice_clients):
            try:
                await vc_item.disconnect(force=True)
            except Exception:
                pass

        try:
            vc_client = await channel.connect(self_mute=self.self_mute, self_deaf=self.self_deaf, timeout=20.0)
            await asyncio.sleep(1.0)

            if vc_client.is_connected():
                self.in_voice = True
                m = " [Muted]" if self.self_mute else ""
                d = " [Deafened]" if self.self_deaf else ""
                push_log(self.account_name, f"BERHASIL stay di #{channel.name} @ {guild.name}{m}{d}!")
                status_map[self.account_name] = {"status": "VOICE", "detail": f"#{channel.name}"}
                return True
            else:
                push_log(self.account_name, f"Koneksi belum stabil di #{channel.name}.")
                status_map[self.account_name] = {"status": "ONLINE", "detail": "Gagal join"}
                return False
        except Exception as e:
            push_log(self.account_name, f"Gagal masuk voice: {e}")
            status_map[self.account_name] = {"status": "ONLINE", "detail": "Join error"}
            return False

    async def action_leave_voice(self):
        self.in_voice = False
        push_log(self.account_name, "Keluar dari voice channel...")
        status_map[self.account_name] = {"status": "ONLINE", "detail": "Standby"}

        for vc_item in list(self.voice_clients):
            try:
                await vc_item.disconnect(force=True)
            except Exception:
                pass

    async def action_stop(self):
        self.is_active = False
        self.in_voice = False
        push_log(self.account_name, "Mematikan koneksi bot...")
        status_map[self.account_name] = {"status": "OFFLINE", "detail": ""}

        for vc_item in list(self.voice_clients):
            try:
                await vc_item.disconnect(force=True)
            except Exception:
                pass
        await self.close()


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
      --success: #23a55a;
      --danger: #da373c;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 14px;
      min-height: 100vh;
    }
    .container { max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: 14px; }
    .header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
    .title h1 { font-size: 19px; font-weight: 700; }
    .title p { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
    .actions { display: flex; gap: 6px; flex-wrap: wrap; }
    button {
      font-family: inherit; font-size: 13px; font-weight: 600; padding: 7px 12px;
      border-radius: 6px; border: none; cursor: pointer; transition: 0.15s;
    }
    .btn-primary { background: var(--primary); color: #fff; }
    .btn-success { background: var(--success); color: #fff; }
    .btn-danger { background: var(--danger); color: #fff; }
    .btn-dark { background: #232936; color: var(--text); }
    .card { background: var(--card); border: 1px solid var(--card-border); border-radius: 8px; overflow: hidden; padding: 14px; }
    .card-title { font-weight: 600; font-size: 13px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
    .item { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--card-border); }
    .item:last-child { border-bottom: none; }
    .status { padding: 2px 7px; border-radius: 10px; font-size: 11px; font-weight: bold; }
    .st-VOICE { background: rgba(35,165,90,0.2); color: #57f287; }
    .st-ONLINE { background: rgba(35,165,90,0.2); color: #57f287; }
    .st-CONNECTING { background: rgba(240,178,50,0.2); color: #fee75c; }
    .st-RECONNECTING { background: rgba(240,178,50,0.2); color: #fee75c; }
    .st-OFFLINE { background: #232936; color: #8b949e; }
    .st-ERROR { background: rgba(218,55,60,0.2); color: #ed4245; }
    .log-box { background: #07090e; border-radius: 6px; padding: 10px; font-family: ui-monospace, Consolas, monospace; font-size: 11px; height: 140px; overflow-y: auto; color: #9cdcfe; line-height: 1.4; }
    input[type=text], input[type=password] { width: 100%; box-sizing: border-box; background: #0b0e14; border: 1px solid var(--card-border); color: #fff; padding: 8px; border-radius: 6px; margin: 4px 0 8px 0; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="title">
        <h1>Discord Voice Stay Manager</h1>
        <p>Login standby otomatis. Klik hijau untuk Join Voice.</p>
      </div>
      <div class="actions">
        <button class="btn-primary" onclick="toggleForm()">+ Akun</button>
        <button class="btn-success" onclick="fetch('/api/join_all',{method:'POST'}).then(load)">Join All</button>
        <button class="btn-danger" onclick="fetch('/api/leave_all',{method:'POST'}).then(load)">Leave All</button>
        <button class="btn-dark" style="color:#ff7b72" onclick="shutdown()">Shutdown</button>
      </div>
    </div>

    <div class="card" id="form-card" style="display: none;">
      <div class="card-title">Tambah / Ubah Akun</div>
      <input type="text" id="acc-name" placeholder="Nama Akun">
      <input type="password" id="acc-token" placeholder="Token Discord">
      <input type="text" id="acc-guild" placeholder="Server ID">
      <input type="text" id="acc-channel" placeholder="Voice Channel ID">
      <div style="display:flex; gap:8px;">
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
        <button class="btn-dark" style="font-size:11px; padding:3px 7px;" onclick="fetch('/api/clear_logs',{method:'POST'}).then(load)">Clear</button>
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
          list.innerHTML = '<p style="color:#8b949e; text-align:center; padding:10px;">Belum ada akun tersimpan.</p>';
          return;
        }
        list.innerHTML = data.accounts.map(a => {
          const s = data.statuses[a.name] || {status: 'OFFLINE', detail: ''};
          let actionBtn = '';
          if (s.status === 'VOICE') {
            actionBtn = `<button class="btn-danger" style="padding:4px 8px; font-size:12px;" onclick="fetch('/api/voice/leave',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'${escape(a.name)}'})}).then(load)">Leave VC</button>`;
          } else if (s.status === 'ONLINE') {
            actionBtn = `<button class="btn-success" style="padding:4px 8px; font-size:12px;" onclick="fetch('/api/voice/join',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'${escape(a.name)}'})}).then(load)">Join Voice</button>`;
          } else {
            actionBtn = `<button class="btn-dark" style="padding:4px 8px; font-size:12px;" disabled>...</button>`;
          }

          return `
            <div class="item">
              <div>
                <strong>${escape(a.name)}</strong><br>
                <span class="status st-${s.status}">${s.status}</span>
                <small style="color:#8b949e; margin-left:4px;">${escape(s.detail)}</small>
              </div>
              <div style="display:flex; gap:5px;">
                ${actionBtn}
                <button class="btn-dark" style="padding:4px 8px; font-size:12px; color:#ff7b72;" onclick="del('${escape(a.name)}')">&times;</button>
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
      if (!name || !token || !guild || !channel) { alert("Semua field wajib diisi!"); return; }

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
      if (!confirm("Matikan server bot?")) return;
      await fetch('/api/shutdown', {method:'POST'});
      document.body.innerHTML = '<div style="text-align:center; padding:40px; color:#8b949e;">Server dimatikan.</div>';
    }

    function escape(s) {
      return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    let isFetching = false;
    async function loopLoad() {
      if (!document.hidden && !isFetching) {
        isFetching = true;
        try { await load(); } catch(e){}
        isFetching = false;
      }
      setTimeout(loopLoad, 2500);
    }
    load();
    setTimeout(loopLoad, 2500);
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
    if name in bots and main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(bots[name].action_join_voice(), main_loop)
    return jsonify({"ok": True})


@app.route("/api/voice/leave", methods=["POST"])
def api_voice_leave():
    name = request.json.get("name")
    if name in bots and main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(bots[name].action_leave_voice(), main_loop)
    return jsonify({"ok": True})


@app.route("/api/join_all", methods=["POST"])
def api_join_all():
    if main_loop and main_loop.is_running():
        for bot_instance in bots.values():
            asyncio.run_coroutine_threadsafe(bot_instance.action_join_voice(), main_loop)
    return jsonify({"ok": True})


@app.route("/api/leave_all", methods=["POST"])
def api_leave_all():
    if main_loop and main_loop.is_running():
        for bot_instance in bots.values():
            asyncio.run_coroutine_threadsafe(bot_instance.action_leave_voice(), main_loop)
    return jsonify({"ok": True})


@app.route("/api/save", methods=["POST"])
def api_save():
    d = request.json
    accs = [a for a in load_accounts() if a["name"] != d["name"]]
    accs.append(d)
    save_accounts(accs)
    if main_loop and main_loop.is_running():
        bot_instance = BotClient(d)
        bots[d["name"]] = bot_instance
        asyncio.run_coroutine_threadsafe(bot_instance.start(d["token"]), main_loop)
    return jsonify({"ok": True})


@app.route("/api/delete", methods=["POST"])
def api_delete():
    name = request.json.get("name")
    if name in bots and main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(bots[name].action_stop(), main_loop)
        del bots[name]
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
    if main_loop and main_loop.is_running():
        for b in list(bots.values()):
            asyncio.run_coroutine_threadsafe(b.action_stop(), main_loop)

    def _exit():
        time.sleep(1)
        os._exit(0)
    threading.Thread(target=_exit, daemon=True).start()
    return jsonify({"ok": True})


def run_flask():
    app.run(host="0.0.0.0", port=5050, debug=False, use_reloader=False, threaded=True)


async def main_async():
    global main_loop
    main_loop = asyncio.get_running_loop()

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("\n" + "=" * 50)
    print("  Discord Voice Stay Multi-Bot")
    print(f"  Direktori: {BASE_DIR}")
    print("  Dashboard: http://127.0.0.1:5050")
    print("=" * 50 + "\n")

    accounts = load_accounts()
    for acc in accounts:
        name = acc["name"]
        token = acc.get("token")
        if not token:
            continue
        bot_instance = BotClient(acc)
        bots[name] = bot_instance
        status_map[name] = {"status": "CONNECTING", "detail": "Login..."}
        asyncio.create_task(bot_instance.start(token))

    if sys.platform == "win32":
        threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open("http://127.0.0.1:5050")), daemon=True).start()

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except (KeyboardInterrupt, SystemExit):
        print("\n[Shutdown] Menutup bot...")
