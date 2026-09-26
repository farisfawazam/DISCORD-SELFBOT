import sys
import os
import site

user_site = site.getusersitepackages()
if os.path.exists(user_site) and user_site not in sys.path:
    sys.path.insert(0, user_site)

import json
import logging
from flask import Flask, jsonify, request, render_template_string

# Ensure path includes root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.storage import load_accounts, save_accounts
from core.bot import BotRunner

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

MAX_LOGS = 200
log_buffer = []
status_map = {}
active_runners = {}


def on_bot_log(name, msg):
    log_buffer.append(msg)
    if len(log_buffer) > MAX_LOGS:
        log_buffer.pop(0)


def on_bot_status(name, status, detail=""):
    status_map[name] = {"status": status, "detail": detail}


app = Flask(__name__)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Discord Voice Multi-Bot</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
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
      --success-hover: #1c8448;
      --danger: #da373c;
      --danger-hover: #b02a2f;
      --warning: #f0b232;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 24px;
      min-height: 100vh;
    }
    .container {
      max-width: 1100px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
      padding-bottom: 8px;
    }
    .title h1 {
      font-size: 22px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .title p {
      font-size: 13px;
      color: var(--text-muted);
      margin-top: 4px;
    }
    .actions { display: flex; gap: 10px; }
    button {
      font-family: inherit;
      font-size: 13px;
      font-weight: 600;
      padding: 9px 16px;
      border-radius: 8px;
      border: none;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }
    .btn-primary { background: var(--primary); color: #fff; }
    .btn-primary:hover { background: var(--primary-hover); }
    .btn-success { background: var(--success); color: #fff; }
    .btn-success:hover { background: var(--success-hover); }
    .btn-danger { background: var(--danger); color: #fff; }
    .btn-danger:hover { background: var(--danger-hover); }
    .btn-secondary { background: #232936; color: var(--text); }
    .btn-secondary:hover { background: #2d3446; }
    .btn-sm { padding: 6px 12px; font-size: 12px; border-radius: 6px; }

    .card {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      overflow: hidden;
    }
    .card-header {
      padding: 16px 20px;
      border-bottom: 1px solid var(--card-border);
      font-size: 15px;
      font-weight: 600;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .table-responsive { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }
    th {
      background: #11141c;
      color: var(--text-muted);
      font-weight: 600;
      padding: 12px 18px;
      border-bottom: 1px solid var(--card-border);
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.5px;
    }
    td { padding: 14px 18px; border-bottom: 1px solid var(--card-border); vertical-align: middle; }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: rgba(255,255,255,0.02); }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.5px;
    }
    .badge-voice { background: rgba(35, 165, 90, 0.2); color: #57f287; }
    .badge-online { background: rgba(35, 165, 90, 0.2); color: #57f287; }
    .badge-connecting { background: rgba(240, 178, 50, 0.2); color: #fee75c; }
    .badge-reconnecting { background: rgba(240, 178, 50, 0.2); color: #fee75c; }
    .badge-error { background: rgba(218, 55, 60, 0.2); color: #ed4245; }
    .badge-offline { background: rgba(139, 148, 158, 0.15); color: #8b949e; }
    .badge-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }

    .log-container {
      background: #07090e;
      padding: 16px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      color: #9cdcfe;
      height: 220px;
      overflow-y: auto;
      line-height: 1.6;
      border-radius: 0 0 12px 12px;
    }

    .modal {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.7);
      backdrop-filter: blur(4px);
      align-items: center;
      justify-content: center;
      z-index: 100;
      padding: 16px;
    }
    .modal.active { display: flex; }
    .modal-content {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      width: 100%;
      max-width: 480px;
      overflow: hidden;
      box-shadow: 0 20px 40px rgba(0,0,0,0.5);
    }
    .modal-header {
      padding: 18px 20px;
      border-bottom: 1px solid var(--card-border);
      font-size: 16px;
      font-weight: 600;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .modal-body {
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .form-group { display: flex; flex-direction: column; gap: 6px; }
    .form-group label {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .form-control {
      background: #0b0e14;
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 10px 14px;
      color: var(--text);
      font-family: inherit;
      font-size: 13px;
      outline: none;
      transition: border-color 0.15s ease;
    }
    .form-control:focus { border-color: var(--primary); }
    .checkbox-group { display: flex; gap: 20px; margin-top: 6px; }
    .checkbox-label {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      cursor: pointer;
    }
    .modal-footer {
      padding: 16px 20px;
      background: #11141c;
      border-top: 1px solid var(--card-border);
      display: flex;
      justify-content: flex-end;
      gap: 10px;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="title">
        <h1>Discord Voice Stay Dashboard</h1>
        <p>Stay in voice channels 24/7 with multiple selfbot accounts</p>
      </div>
      <div class="actions">
        <button class="btn-primary" onclick="openAddModal()">+ Add Account</button>
        <button class="btn-success" onclick="startAll()">Start All</button>
        <button class="btn-danger" onclick="stopAll()">Stop All</button>
        <button class="btn-secondary" style="border: 1px solid var(--danger); color: #ff7b72;" onclick="shutdownServer()">Shutdown Server</button>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span>Accounts List</span>
        <span id="account-count" style="font-size: 12px; color: var(--text-muted);">Loading...</span>
      </div>
      <div class="table-responsive">
        <table>
          <thead>
            <tr>
              <th>Account</th>
              <th>Status</th>
              <th>Detail</th>
              <th>Audio</th>
              <th>Server / Channel</th>
              <th style="text-align: right;">Action</th>
            </tr>
          </thead>
          <tbody id="accounts-body">
            <tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">Loading accounts...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span>Live Console Output</span>
        <button class="btn-secondary btn-sm" onclick="clearLogs()">Clear Log</button>
      </div>
      <div class="log-container" id="log-box"></div>
    </div>
  </div>

  <div class="modal" id="account-modal">
    <div class="modal-content">
      <div class="modal-header">
        <span id="modal-title">Add Account</span>
        <span style="cursor: pointer; font-size: 18px;" onclick="closeModal()">&times;</span>
      </div>
      <div class="modal-body">
        <input type="hidden" id="edit-original-name">
        <div class="form-group">
          <label>Account Name</label>
          <input type="text" id="acc-name" class="form-control" placeholder="e.g. Akun Utama">
        </div>
        <div class="form-group">
          <label>Discord Token</label>
          <input type="password" id="acc-token" class="form-control" placeholder="Paste Discord token">
        </div>
        <div class="form-group">
          <label>Server (Guild) ID</label>
          <input type="text" id="acc-guild" class="form-control" placeholder="e.g. 1480117702646435921">
        </div>
        <div class="form-group">
          <label>Voice Channel ID</label>
          <input type="text" id="acc-channel" class="form-control" placeholder="e.g. 1552797076537090108">
        </div>
        <div class="checkbox-group">
          <label class="checkbox-label">
            <input type="checkbox" id="acc-mute" checked> Self Mute
          </label>
          <label class="checkbox-label">
            <input type="checkbox" id="acc-deaf" checked> Self Deafen
          </label>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn-primary" onclick="saveAccount()">Save Account</button>
      </div>
    </div>
  </div>

  <script>
    let currentAccounts = [];

    async function loadData() {
      try {
        const res = await fetch('/api/state');
        const data = await res.json();
        currentAccounts = data.accounts;
        renderAccounts(data.accounts, data.statuses);
        renderLogs(data.logs);
      } catch (e) {}
    }

    function renderAccounts(accounts, statuses) {
      document.getElementById('account-count').innerText = `${accounts.length} account(s)`;
      const tbody = document.getElementById('accounts-body');
      if (accounts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">Belum ada akun tersimpan. Klik "+ Add Account" di atas.</td></tr>';
        return;
      }
      tbody.innerHTML = accounts.map(acc => {
        const st = statuses[acc.name] || { status: 'OFFLINE', detail: '' };
        const badgeClass = 'badge-' + st.status.toLowerCase();
        const isRunning = ['VOICE', 'ONLINE', 'CONNECTING', 'RECONNECTING'].includes(st.status);
        const audioStr = (acc.self_mute !== false ? 'Muted' : 'Live') + ' / ' + (acc.self_deaf !== false ? 'Deaf' : 'Open');
        
        return `
          <tr>
            <td><strong>${escapeHtml(acc.name)}</strong></td>
            <td>
              <span class="badge ${badgeClass}">
                <span class="badge-dot"></span>
                ${st.status}
              </span>
            </td>
            <td style="color: var(--text-muted); font-size: 12px;">${escapeHtml(st.detail || '-')}</td>
            <td style="font-size: 12px; color: var(--text-muted);">${audioStr}</td>
            <td style="font-family: monospace; font-size: 11px; color: var(--text-muted);">
              <div>G: ${acc.guild_id}</div>
              <div>C: ${acc.channel_id}</div>
            </td>
            <td style="text-align: right; white-space: nowrap;">
              ${isRunning 
                ? `<button class="btn-danger btn-sm" onclick="stopAccount('${escapeHtml(acc.name)}')">Stop</button>`
                : `<button class="btn-success btn-sm" onclick="startAccount('${escapeHtml(acc.name)}')">Start</button>`
              }
              <button class="btn-secondary btn-sm" onclick="openEditModal('${escapeHtml(acc.name)}')">Edit</button>
              <button class="btn-secondary btn-sm" style="color: var(--danger);" onclick="deleteAccount('${escapeHtml(acc.name)}')">&times;</button>
            </td>
          </tr>
        `;
      }).join('');
    }

    function renderLogs(logs) {
      const box = document.getElementById('log-box');
      const isScrolledToBottom = box.scrollHeight - box.clientHeight <= box.scrollTop + 30;
      box.innerHTML = logs.map(l => `<div>${escapeHtml(l)}</div>`).join('');
      if (isScrolledToBottom) {
        box.scrollTop = box.scrollHeight;
      }
    }

    async function startAccount(name) {
      await fetch('/api/account/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name })
      });
      loadData();
    }

    async function stopAccount(name) {
      await fetch('/api/account/stop', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name })
      });
      loadData();
    }

    async function startAll() {
      await fetch('/api/action/start_all', { method: 'POST' });
      loadData();
    }

    async function stopAll() {
      await fetch('/api/action/stop_all', { method: 'POST' });
      loadData();
    }

    async function shutdownServer() {
      if (!confirm("Yakin ingin mematikan Localhost Server & semua bot yang sedang jalan?")) return;
      try {
        await fetch('/api/action/shutdown', { method: 'POST' });
      } catch (e) {}
      document.body.innerHTML = `
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:80vh;font-family:sans-serif;color:#e6edf3;text-align:center;">
          <h2 style="margin-bottom:12px;">Server Telah Dimatikan</h2>
          <p style="color:#8b949e;">Semua koneksi Discord telah ditutup dan server localhost sudah berhenti.</p>
          <p style="color:#8b949e;margin-top:8px;">Lo bisa menutup tab browser ini sekarang.</p>
        </div>
      `;
    }

    async function clearLogs() {
      await fetch('/api/action/clear_logs', { method: 'POST' });
      loadData();
    }

    async function deleteAccount(name) {
      if (!confirm(`Hapus akun '${name}'?`)) return;
      await fetch('/api/account/delete', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name })
      });
      loadData();
    }

    function openAddModal() {
      document.getElementById('modal-title').innerText = 'Add Account';
      document.getElementById('edit-original-name').value = '';
      document.getElementById('acc-name').value = '';
      document.getElementById('acc-token').value = '';
      document.getElementById('acc-guild').value = '';
      document.getElementById('acc-channel').value = '';
      document.getElementById('acc-mute').checked = true;
      document.getElementById('acc-deaf').checked = true;
      document.getElementById('account-modal').classList.add('active');
    }

    function openEditModal(name) {
      const acc = currentAccounts.find(a => a.name === name);
      if (!acc) return;
      document.getElementById('modal-title').innerText = 'Edit Account';
      document.getElementById('edit-original-name').value = acc.name;
      document.getElementById('acc-name').value = acc.name;
      document.getElementById('acc-token').value = acc.token;
      document.getElementById('acc-guild').value = acc.guild_id;
      document.getElementById('acc-channel').value = acc.channel_id;
      document.getElementById('acc-mute').checked = acc.self_mute !== false;
      document.getElementById('acc-deaf').checked = acc.self_deaf !== false;
      document.getElementById('account-modal').classList.add('active');
    }

    function closeModal() {
      document.getElementById('account-modal').classList.remove('active');
    }

    async function saveAccount() {
      const original_name = document.getElementById('edit-original-name').value;
      const data = {
        original_name,
        name: document.getElementById('acc-name').value.trim(),
        token: document.getElementById('acc-token').value.trim(),
        guild_id: document.getElementById('acc-guild').value.trim(),
        channel_id: document.getElementById('acc-channel').value.trim(),
        self_mute: document.getElementById('acc-mute').checked,
        self_deaf: document.getElementById('acc-deaf').checked,
      };

      if (!data.name || !data.token || !data.guild_id || !data.channel_id) {
        alert("Semua field wajib diisi!");
        return;
      }

      const res = await fetch('/api/account/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
      });
      const result = await res.json();
      if (result.error) {
        alert(result.error);
        return;
      }
      closeModal();
      loadData();
    }

    function escapeHtml(str) {
      return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    loadData();
    setInterval(loadData, 1500);
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/state")
def get_state():
    accs = load_accounts()
    safe_accs = []
    for a in accs:
        c = dict(a)
        t = c.get("token", "")
        c["token_masked"] = (t[:8] + "..." + t[-4:]) if len(t) > 12 else "***"
        safe_accs.append(c)
    return jsonify({
        "accounts": safe_accs,
        "statuses": status_map,
        "logs": log_buffer
    })


@app.route("/api/account/start", methods=["POST"])
def api_start_account():
    name = request.json.get("name")
    accs = load_accounts()
    acc = next((a for a in accs if a["name"] == name), None)
    if not acc:
        return jsonify({"error": "Account not found"}), 404

    if name in active_runners and active_runners[name].running:
        return jsonify({"ok": True, "msg": "Already running"})

    runner = BotRunner(acc, on_log=on_bot_log, on_status=on_bot_status)
    active_runners[name] = runner
    runner.start()
    return jsonify({"ok": True})


@app.route("/api/account/stop", methods=["POST"])
def api_stop_account():
    name = request.json.get("name")
    if name in active_runners:
        active_runners[name].stop()
        on_bot_status(name, "OFFLINE", "")
    return jsonify({"ok": True})


@app.route("/api/action/start_all", methods=["POST"])
def api_start_all():
    accs = load_accounts()
    for acc in accs:
        name = acc["name"]
        if name not in active_runners or not active_runners[name].running:
            runner = BotRunner(acc, on_log=on_bot_log, on_status=on_bot_status)
            active_runners[name] = runner
            runner.start()
    return jsonify({"ok": True})


@app.route("/api/action/stop_all", methods=["POST"])
def api_stop_all():
    for runner in active_runners.values():
        runner.stop()
    for acc in load_accounts():
        on_bot_status(acc["name"], "OFFLINE", "")
    return jsonify({"ok": True})


@app.route("/api/action/clear_logs", methods=["POST"])
def api_clear_logs():
    global log_buffer
    log_buffer = []
    return jsonify({"ok": True})


@app.route("/api/account/save", methods=["POST"])
def api_save_account():
    data = request.json
    orig = data.get("original_name")
    name = data.get("name")
    token = data.get("token")
    guild_id = data.get("guild_id")
    channel_id = data.get("channel_id")
    self_mute = data.get("self_mute", True)
    self_deaf = data.get("self_deaf", True)

    accs = load_accounts()

    if name != orig and any(a["name"] == name for a in accs):
        return jsonify({"error": f"Nama akun '{name}' sudah ada!"}), 400

    new_entry = {
        "name": name,
        "token": token,
        "guild_id": guild_id,
        "channel_id": channel_id,
        "self_mute": self_mute,
        "self_deaf": self_deaf
    }

    if orig:
        if orig in active_runners:
            active_runners[orig].stop()
            del active_runners[orig]
        accs = [new_entry if a["name"] == orig else a for a in accs]
    else:
        accs.append(new_entry)

    save_accounts(accs)
    return jsonify({"ok": True})


@app.route("/api/account/delete", methods=["POST"])
def api_delete_account():
    name = request.json.get("name")
    if name in active_runners:
        active_runners[name].stop()
        del active_runners[name]
    accs = [a for a in load_accounts() if a["name"] != name]
    save_accounts(accs)
    if name in status_map:
        del status_map[name]
    return jsonify({"ok": True})


@app.route("/api/action/shutdown", methods=["POST"])
def api_shutdown():
    # Stop all bots first
    for runner in active_runners.values():
        runner.stop()
    
    # Schedule process exit after response is returned
    import threading, time
    def _kill():
        time.sleep(1)
        os._exit(0)
    threading.Thread(target=_kill, daemon=True).start()

    return jsonify({"ok": True, "msg": "Shutting down..."})


def run_server(port=5050):
    # Auto start all accounts on launch
    try:
        accs = load_accounts()
        for acc in accs:
            name = acc["name"]
            runner = BotRunner(acc, on_log=on_bot_log, on_status=on_bot_status)
            active_runners[name] = runner
            runner.start()
    except Exception as e:
        on_bot_log("SYSTEM", f"Auto-start error: {e}")

    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    run_server()
