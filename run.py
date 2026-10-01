import sys
import os
import site
import json
import asyncio
import logging
import types
import time
from datetime import datetime

# Pastikan path user site-packages terbaca
user_site = site.getusersitepackages()
if os.path.exists(user_site) and user_site not in sys.path:
    sys.path.insert(0, user_site)

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
else:
    try:
        import subprocess
        subprocess.run(["termux-wake-lock"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

# Dummy audioop stub untuk Python 3.13/3.14
if "audioop" not in sys.modules:
    m_audioop = types.ModuleType("audioop")
    m_audioop.error = Exception
    sys.modules["audioop"] = m_audioop

# Universal PyNaCl Mock (bypass libsodium / C-compiler untuk Android Termux & VPS headless)
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

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

console = Console(legacy_windows=False)

import aiohttp
import discord
import discord.voice_client as vc
from discord.ext import commands
from discord import utils

vc.has_nacl = True
logging.getLogger("discord").setLevel(logging.WARNING)

# ==============================================================================
# 1. PURE AIOHTTP GATEWAY & HTTP CLIENT (Bypass curl_cffi untuk Cross-Platform)
# ==============================================================================
class AsyncWsWrapper:
    def __init__(self, ws):
        self._ws = ws

    @property
    def closed(self): return self._ws.closed
    @property
    def close_code(self): return self._ws.close_code
    @property
    def close_reason(self): return ""

    async def send(self, data):
        if isinstance(data, str): return await self._ws.send_str(data)
        return await self._ws.send_bytes(data)

    async def send_str(self, data):
        if isinstance(data, (bytes, bytearray)): data = data.decode("utf-8", errors="replace")
        return await self._ws.send_str(str(data))

    async def send_bytes(self, data):
        if isinstance(data, str): data = data.encode("utf-8")
        return await self._ws.send_bytes(data)

    async def recv(self):
        msg = await self._ws.receive()
        if msg.type == aiohttp.WSMsgType.TEXT:
            return msg.data.encode("utf-8"), 1
        elif msg.type == aiohttp.WSMsgType.BINARY:
            return msg.data, 2
        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSE):
            return b"", 8
        return msg.data if isinstance(msg.data, (bytes, bytearray)) else str(msg.data).encode("utf-8"), 1

    async def close(self, code=1000, reason=""):
        msg = reason.encode("utf-8") if isinstance(reason, str) else reason
        return await self._ws.close(code=code, message=msg)

    def __getattr__(self, name):
        return getattr(self._ws, name)


class AiohttpCompatSession:
    def __init__(self, raw_session):
        self._s = raw_session

    async def request(self, method, url, **kwargs):
        kwargs.pop("stream", None)
        kwargs.pop("interface", None)
        kwargs.pop("impersonate", None)
        kwargs.pop("default_headers", None)
        resp = await self._s.request(method, url, **kwargs)
        resp.status_code = resp.status
        return resp

    async def ws_connect(self, url, **kwargs):
        kwargs.pop("interface", None)
        kwargs.pop("impersonate", None)
        kwargs.pop("timeout", None)
        headers = kwargs.pop("headers", {})
        ws = await self._s.ws_connect(url, headers=headers)
        return AsyncWsWrapper(ws)

    def __getattr__(self, name):
        return getattr(self._s, name)


async def _patched_startup(self):
    if self._started: return
    self._global_over = asyncio.Event()
    self._global_over.set()
    if self.connector is discord.utils.MISSING or self.connector.closed:
        self.connector = aiohttp.TCPConnector(limit=0)
    raw_s = await discord.http._gen_session(aiohttp.ClientSession(connector=self.connector))
    self.headers = await utils.Headers.default(raw_s, self.proxy, self.proxy_auth)
    self._HTTPClient__session = AiohttpCompatSession(raw_s)
    self._started = True

discord.http.HTTPClient.startup = _patched_startup

# ==============================================================================
# 2. PURE VOICE STAY PROTOCOL (Official Discord Voice v8 Heartbeat 24/7)
# ==============================================================================
class PureVoiceStayProtocol(discord.VoiceProtocol):
    def __init__(self, client, channel):
        super().__init__(client, channel)
        self.channel = channel
        self.client = client
        self.session_id = None
        self.token = None
        self.endpoint = None
        self.ws = None
        self.is_connected_flag = False
        self.hb_task = None
        self.ws_task = None

    async def on_voice_state_update(self, data):
        self.session_id = data.get("session_id")

    async def on_voice_server_update(self, data):
        self.token = data.get("token")
        self.endpoint = data.get("endpoint")
        if self.endpoint:
            if self.ws_task and not self.ws_task.done():
                self.ws_task.cancel()
            self.ws_task = asyncio.create_task(self._connect_voice_ws())

    async def _connect_voice_ws(self):
        url = f"wss://{self.endpoint}/?v=8"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(url) as ws:
                    self.ws = ws
                    hello = await ws.receive_json()
                    interval = hello["d"]["heartbeat_interval"] / 1000.0

                    identify = {
                        "op": 0,
                        "d": {
                            "server_id": str(self.channel.guild.id),
                            "user_id": str(self.client.user.id),
                            "session_id": self.session_id,
                            "token": self.token,
                            "max_dave_protocol_version": 1
                        }
                    }
                    await ws.send_json(identify)

                    async def _heartbeat_loop():
                        seq = -1
                        while not ws.closed:
                            await asyncio.sleep(interval)
                            nonce = int(asyncio.get_event_loop().time() * 1000)
                            try:
                                await ws.send_json({"op": 3, "d": {"t": nonce, "seq_ack": seq}})
                            except Exception:
                                break

                    self.hb_task = asyncio.create_task(_heartbeat_loop())

                    while not ws.closed:
                        msg = await ws.receive()
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("op") == 2:
                                self.is_connected_flag = True
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE):
                            break
                    if self.hb_task:
                        self.hb_task.cancel()
        except Exception:
            pass

    async def connect(self, *, timeout=30.0, reconnect=True, self_deaf=False, self_mute=False):
        await self.channel.guild.change_voice_state(channel=self.channel, self_mute=self_mute, self_deaf=self_deaf)
        return self

    async def disconnect(self, *, force=False):
        self.is_connected_flag = False
        if self.hb_task and not self.hb_task.done():
            self.hb_task.cancel()
        if self.ws and not self.ws.closed:
            await self.ws.close()
        try:
            await self.channel.guild.change_voice_state(channel=None)
        except Exception:
            pass

    def is_connected(self):
        return self.is_connected_flag

# ==============================================================================
# 3. DATABASE & SETTINGS MANAGEMENT
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_FILE = os.path.join(BASE_DIR, "accounts.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "stagger_delay": 2.0,
    "max_reconnect_attempts": 10,
    "auto_wake_lock": True,
}


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                res = DEFAULT_SETTINGS.copy()
                res.update(d)
                return res
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()


def save_settings(s):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)


def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for a in data:
                        if "enabled" not in a:
                            a["enabled"] = True
                        if "presence" not in a:
                            a["presence"] = "online"
                    return data
        except Exception:
            return []
    return []


def save_accounts(accs):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accs, f, indent=2, ensure_ascii=False)


def mask_token(token):
    if not token:
        return ""
    if len(token) > 12:
        return f"{token[:6]}...{token[-4:]}"
    return "***"


def log_event(bot_name, log_type, message):
    ts = datetime.now().strftime("%H:%M:%S")
    colors = {
        "AUTH": "#5865F2",
        "GATEWAY": "#00F0FF",
        "LOGIN": "#23A55A",
        "VOICE": "#57F287",
        "STAY": "#00D26A",
        "HEARTBEAT": "#FEE75C",
        "RECONNECT": "#FEE75C",
        "WARN": "#FEE75C",
        "ERROR": "#DA373C",
        "SYS": "#5865F2",
    }
    color = colors.get(log_type, "white")
    name_tag = f"[[bold #5865F2]{bot_name}[/]]"
    console.print(f"{name_tag} [dim]{ts}[/dim] [[bold {color}]{log_type:<9}[/]] {message}")

# ==============================================================================
# 4. BOT CORE RUNNER
# ==============================================================================
class VoiceStayBot(commands.Bot):
    def __init__(self, acc, settings):
        self.acc = acc
        self.bot_settings = settings
        self.account_name = acc["name"]
        self.token = acc["token"]
        self.guild_id = int(acc["guild_id"])
        self.channel_id = int(acc["channel_id"])
        self.self_mute = acc.get("self_mute", True)
        self.self_deaf = acc.get("self_deaf", True)
        self.presence = acc.get("presence", "online")
        self.in_voice = False
        self.target_voice = True
        self.current_vc = None
        self.reconnect_count = 0

        super().__init__(
            command_prefix="!",
            self_bot=True,
            chunk_guilds_at_startup=False,
            member_cache_flags=discord.MemberCacheFlags.none(),
            max_messages=None,
            sync_presence=False,
        )

    async def on_ready(self):
        status_map = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible,
        }
        chosen_status = status_map.get(self.presence.lower(), discord.Status.online)
        try:
            await self.change_presence(status=chosen_status)
        except Exception:
            pass

        log_event(self.account_name, "LOGIN", f"Login sukses sebagai [bold white]{self.user}[/] | Status: [#00F0FF]{self.presence.upper()}[/]")
        if self.target_voice:
            await self.action_join_voice()

    async def on_voice_state_update(self, member, before, after):
        if member.id == self.user.id:
            if after.channel is not None:
                self.in_voice = True
                self.reconnect_count = 0
            else:
                self.in_voice = False
                max_rec = self.bot_settings.get("max_reconnect_attempts", 10)
                if self.target_voice and not self.is_closed():
                    self.reconnect_count += 1
                    if self.reconnect_count > max_rec:
                        log_event(self.account_name, "ERROR", f"Batas reconnect tercapai ({max_rec}x). Menghentikan auto-reconnect.")
                        return

                    delay = min(self.reconnect_count * 2.5, 30)
                    log_event(self.account_name, "RECONNECT", f"Koneksi voice terputus. Mencoba reconnect #{self.reconnect_count} dalam {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    if self.target_voice and not self.is_closed():
                        await self.action_join_voice()

    async def action_join_voice(self):
        guild = self.get_guild(self.guild_id)
        if not guild:
            log_event(self.account_name, "ERROR", f"Server ID {self.guild_id} tidak ditemukan pada akun ini!")
            return False

        channel = guild.get_channel(self.channel_id)
        if not channel:
            log_event(self.account_name, "ERROR", f"Voice Channel ID {self.channel_id} tidak ditemukan di server '{guild.name}'!")
            return False

        log_event(self.account_name, "VOICE", f"Menghubungkan ke [#00F0FF]#{channel.name}[/] @ [#5865F2]{guild.name}[/]...")

        def _check_joined(member, before, after):
            return member.id == self.user.id and after.channel is not None and after.channel.id == channel.id

        try:
            connect_coro = channel.connect(cls=PureVoiceStayProtocol, self_mute=self.self_mute, self_deaf=self.self_deaf)
            wait_vc_coro = self.wait_for("voice_state_update", check=_check_joined, timeout=14.0)
            vc_result, _ = await asyncio.gather(connect_coro, wait_vc_coro)
            self.current_vc = vc_result
            self.in_voice = True
            m = " [#DA373C][Muted][/]" if self.self_mute else " [#23A55A][Open][/]"
            d = " [#DA373C][Deafened][/]" if self.self_deaf else " [#23A55A][Open][/]"
            log_event(self.account_name, "STAY", f"TERHUBUNG di [bold #57F287]#{channel.name}[/] @ {guild.name}{m}{d} (Voice v8 Keepalive Aktif)")
            return True
        except asyncio.TimeoutError:
            log_event(self.account_name, "ERROR", f"Timeout: Server Discord belum merespons join #{channel.name}")
            return False
        except Exception as e:
            log_event(self.account_name, "ERROR", f"Gagal masuk voice: {e}")
            return False

    async def action_stop(self):
        self.target_voice = False
        self.in_voice = False
        if self.current_vc:
            try:
                await self.current_vc.disconnect(force=True)
            except Exception:
                pass
            self.current_vc = None
        guild = self.get_guild(self.guild_id)
        if guild:
            try:
                await guild.change_voice_state(channel=None)
            except Exception:
                pass
        await self.close()


async def run_bots(accounts, settings):
    active_accounts = [a for a in accounts if a.get("enabled", True)]
    if not active_accounts:
        console.print("[bold #DA373C][!] Tidak ada akun aktif (enabled) untuk dijalankan.[/]")
        time.sleep(2)
        return

    clean_screen()
    show_banner()
    stagger = settings.get("stagger_delay", 2.0)
    console.print(Panel(
        f"[bold #23A55A]Memulai sesi Voice Stay untuk {len(active_accounts)} akun aktif[/]\n"
        f"[dim]Stagger Delay: {stagger}s  •  Heartbeat: Discord Voice v8  •  Auto-Reconnect: Aktif[/dim]\n"
        "[bold white]Tekan [/][bold #DA373C]Ctrl+C[/][bold white] kapan saja untuk menghentikan bot dan kembali ke menu.[/]",
        border_style="#5865F2",
        title="[bold #5865F2]LIVE RUNNER SESSION[/]",
        title_align="left",
    ))

    bots = [VoiceStayBot(acc, settings) for acc in active_accounts]

    async def _safe_start(b, delay_sec):
        if delay_sec > 0:
            await asyncio.sleep(delay_sec)
        try:
            log_event(b.account_name, "AUTH", "Mengautentikasi token ke Discord Gateway...")
            await b.start(b.token)
        except discord.LoginFailure:
            log_event(b.account_name, "ERROR", "Token Discord tidak valid atau expired!")
        except Exception as e:
            log_event(b.account_name, "ERROR", f"Sesi bot terhenti: {e}")

    tasks = [asyncio.create_task(_safe_start(b, i * stagger)) for i, b in enumerate(bots)]

    try:
        await asyncio.gather(*tasks)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        console.print("\n[bold #FEE75C][!] Menghentikan bot dan membersihkan sesi voice...[/]")
        await asyncio.gather(*(b.action_stop() for b in bots), return_exceptions=True)
        console.print("[bold #23A55A][OK] Semua sesi voice telah ditutup dengan bersih.[/]\n")
        time.sleep(1.5)

# ==============================================================================
# 5. DISCORD VOICE STAY THEME & TERMINAL LAYOUT
# ==============================================================================
LOGO_ART = r"""
 [bold #5865F2]██╗   ██╗ ██████╗ ██╗ ██████╗███████╗    ███████╗████████╗ █████╗ ██╗   ██╗[/]
 [bold #5865F2]██║   ██║██╔═══██╗██║██╔════╝██╔════╝    ██╔════╝╚══██╔══╝██╔══██╗╚██╗ ██╔╝[/]
 [bold #4752C4]██║   ██║██║   ██║██║██║     █████╗      ███████╗   ██║   ███████║ ╚████╔╝ [/]
 [bold #00D26A]╚██╗ ██╔╝██║   ██║██║██║     ██╔══╝      ╚════██║   ██║   ██╔══██║  ╚██╔╝  [/]
 [bold #00D26A] ╚████╔╝ ╚██████╔╝██║╚██████╗███████╗    ███████║   ██║   ██║  ██║   ██║   [/]
 [bold #23A55A]  ╚═══╝   ╚═════╝ ╚═╝ ╚═════╝╚══════╝    ╚══════╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝   [/]
 [dim #8B949E]─────────────────────────────────────────────────────────────────────────────[/]
 [bold white]DISCORD VOICE STAY MANAGER[/] [dim]•[/] [#57F287]24/7 Official Voice v8 Protocol[/]
 [dim #8B949E]─────────────────────────────────────────────────────────────────────────────[/]"""


def clean_screen():
    os.system("cls" if os.name == "nt" else "clear")


def detect_platform():
    if "TERMUX_VERSION" in os.environ or "com.termux" in os.environ.get("PREFIX", ""):
        return "Mobile (Termux)"
    elif sys.platform.startswith("linux"):
        return "Linux VPS (Server)"
    elif sys.platform == "darwin":
        return "macOS"
    elif os.name == "nt":
        return "PC (Windows)"
    return f"Unknown ({sys.platform})"


def show_banner():
    clean_screen()
    console.print(LOGO_ART)
    console.print("")


def show_accounts_table(accounts):
    if not accounts:
        console.print("[dim]Belum ada akun tersimpan di accounts.json.[/dim]\n")
        return

    table = Table(
        border_style="#5865F2",
        header_style="bold #5865F2",
        title="[bold #5865F2]DISCORD ACCOUNTS CONFIGURATION[/bold #5865F2]",
        title_justify="left",
    )
    table.add_column("No", justify="center", style="bold #FEE75C", no_wrap=True)
    table.add_column("Nama Akun", style="bold white", no_wrap=True)
    table.add_column("Server ID", style="#00F0FF", no_wrap=True)
    table.add_column("Voice ID", style="#00F0FF", no_wrap=True)
    table.add_column("Audio State", justify="center", no_wrap=True)
    table.add_column("Presence", justify="center", no_wrap=True)
    table.add_column("Token", style="dim", no_wrap=True)
    table.add_column("Status", justify="center", no_wrap=True)

    for idx, acc in enumerate(accounts, 1):
        tk = acc.get("token", "")
        preview = mask_token(tk)
        m = "[#DA373C]Muted[/]" if acc.get("self_mute", True) else "[#23A55A]Open[/]"
        d = "[#DA373C]Deaf[/]" if acc.get("self_deaf", True) else "[#23A55A]Open[/]"
        audio_str = f"{m} | {d}"
        presence = acc.get("presence", "online").upper()
        p_color = {"ONLINE": "#23A55A", "IDLE": "#FEE75C", "DND": "#DA373C", "INVISIBLE": "#8B949E"}.get(presence, "#23A55A")
        presence_str = f"[{p_color}]{presence}[/]"
        active = "[bold #23A55A]ENABLED[/]" if acc.get("enabled", True) else "[bold #DA373C]DISABLED[/]"
        table.add_row(
            str(idx),
            acc.get("name", f"Account {idx}"),
            str(acc.get("guild_id", "")),
            str(acc.get("channel_id", "")),
            audio_str,
            presence_str,
            preview,
            active,
        )
    console.print(table)
    console.print("")


async def verify_single_account(acc):
    token = acc.get("token", "").strip()
    if not token:
        return False, "Token kosong", "N/A", "N/A"
    headers = {"Authorization": token, "User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://discord.com/api/v9/users/@me", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    uname = data.get("username", "Unknown")
                    disc = data.get("discriminator", "0")
                    tag = f"{uname}#{disc}" if disc != "0" else uname

                    guild_id = acc.get("guild_id")
                    guild_status = "N/A"
                    if guild_id:
                        async with session.get(f"https://discord.com/api/v9/guilds/{guild_id}", headers=headers) as g_resp:
                            if g_resp.status == 200:
                                g_data = await g_resp.json()
                                guild_status = f"{g_data.get('name', guild_id)}"
                            else:
                                guild_status = f"Err ({g_resp.status})"

                    channel_id = acc.get("channel_id")
                    channel_status = "N/A"
                    if channel_id:
                        async with session.get(f"https://discord.com/api/v9/channels/{channel_id}", headers=headers) as c_resp:
                            if c_resp.status == 200:
                                c_data = await c_resp.json()
                                channel_status = f"#{c_data.get('name', channel_id)}"
                            else:
                                channel_status = f"Err ({c_resp.status})"

                    return True, tag, guild_status, channel_status
                elif resp.status == 401:
                    return False, "Token Invalid (401)", "N/A", "N/A"
                elif resp.status == 403:
                    return False, "Locked / Phone Required (403)", "N/A", "N/A"
                else:
                    return False, f"API Error (HTTP {resp.status})", "N/A", "N/A"
        except Exception as e:
            return False, f"Error: {e}", "N/A", "N/A"


def run_account_verifier():
    accounts = load_accounts()
    show_banner()
    console.print(Panel("[bold #00F0FF]VERIFIKASI TOKEN & SERVER ACCESS[/]\n[dim]Memeriksa validitas token langsung ke Discord API...[/dim]", border_style="#5865F2"))
    if not accounts:
        console.print("[dim]Belum ada akun untuk diverifikasi.[/dim]\n")
        Prompt.ask("Tekan Enter untuk kembali")
        return

    v_table = Table(border_style="#5865F2", header_style="bold #5865F2", title_justify="left")
    v_table.add_column("No", justify="center", style="bold #FEE75C")
    v_table.add_column("Nama Akun", style="bold white")
    v_table.add_column("Discord User", style="#23A55A")
    v_table.add_column("Server", style="#00F0FF")
    v_table.add_column("Channel", style="#00F0FF")
    v_table.add_column("Hasil", justify="center")

    for i, a in enumerate(accounts, 1):
        with console.status(f"[cyan]Memeriksa akun {a['name']}..."):
            ok, user_tag, g_name, c_name = asyncio.run(verify_single_account(a))

        if ok:
            status_badge = "[bold #23A55A]VALID[/]"
        else:
            status_badge = "[bold #DA373C]FAIL[/]"

        v_table.add_row(str(i), a["name"], user_tag, g_name, c_name, status_badge)

    console.print(v_table)
    console.print("")
    try:
        Prompt.ask("[dim]Tekan Enter untuk kembali ke menu[/dim]")
    except (KeyboardInterrupt, EOFError):
        pass


def account_manager():
    while True:
        accounts = load_accounts()
        show_banner()
        console.print(Panel(
            "[bold white]ACCOUNT MANAGEMENT DASHBOARD[/]\n"
            "[dim]Kelola token, server target, default audio mute/deaf, dan presence Discord.[/dim]",
            border_style="#5865F2",
            title="[bold #5865F2]SETTINGS[/]",
            title_align="left",
        ))
        show_accounts_table(accounts)

        console.print("[bold #5865F2][1][/] Tambah Akun Baru")
        console.print("[bold #5865F2][2][/] Edit Akun (Token, Server, Channel, Audio, Presence)")
        console.print("[bold #5865F2][3][/] Toggle Enable/Disable")
        console.print("[bold #5865F2][4][/] Toggle Mic & Audio (Mute / Deafen)")
        console.print("[bold #5865F2][5][/] Ubah Presence Status (Online / Idle / DND / Invisible)")
        console.print("[bold #5865F2][6][/] Hapus Akun")
        console.print("[bold #5865F2][0][/] Kembali ke Menu Utama\n")

        action = Prompt.ask("Pilih aksi", choices=["1", "2", "3", "4", "5", "6", "0"], default="0")

        if action == "1":
            name = Prompt.ask("Nama Label Akun").strip()
            if not name:
                console.print("[#DA373C]Nama akun tidak boleh kosong.[/]")
                time.sleep(1)
                continue
            token = Prompt.ask("Token Discord").strip()
            if (token.startswith('"') and token.endswith('"')) or (token.startswith("'") and token.endswith("'")):
                token = token[1:-1]
            if not token:
                console.print("[#DA373C]Token tidak boleh kosong.[/]")
                time.sleep(1)
                continue
            guild_id = Prompt.ask("Server ID (Guild ID)").strip()
            channel_id = Prompt.ask("Voice Channel ID").strip()
            if not guild_id.isdigit() or not channel_id.isdigit():
                console.print("[#DA373C]Server ID dan Channel ID harus berupa angka![/]")
                time.sleep(1)
                continue

            self_mute = Confirm.ask("Self Mute mic secara default?", default=True)
            self_deaf = Confirm.ask("Self Deafen audio secara default?", default=True)
            presence = Prompt.ask("Discord Status Presence", choices=["online", "idle", "dnd", "invisible"], default="online")

            accounts.append({
                "name": name,
                "token": token,
                "guild_id": guild_id,
                "channel_id": channel_id,
                "self_mute": self_mute,
                "self_deaf": self_deaf,
                "presence": presence,
                "enabled": True,
            })
            save_accounts(accounts)
            console.print(f"[bold #23A55A]✓ Akun '{name}' berhasil disimpan![/]")
            time.sleep(1)

        elif action == "2":
            if not accounts:
                continue
            pick = Prompt.ask("Nomor akun yang ingin diedit", default="1")
            try:
                idx = int(pick) - 1
                if 0 <= idx < len(accounts):
                    acc = accounts[idx]
                    console.print(f"\n[bold #00F0FF]Edit Akun: {acc['name']}[/] [dim](Enter untuk mempertahankan nilai lama)[/dim]")
                    new_name = Prompt.ask("Nama Akun", default=acc["name"]).strip()
                    new_token = Prompt.ask("Token Discord", default=acc["token"]).strip()
                    if (new_token.startswith('"') and new_token.endswith('"')) or (new_token.startswith("'") and new_token.endswith("'")):
                        new_token = new_token[1:-1]
                    new_guild = Prompt.ask("Server ID", default=str(acc["guild_id"])).strip()
                    new_channel = Prompt.ask("Voice Channel ID", default=str(acc["channel_id"])).strip()
                    new_mute = Confirm.ask("Self Mute?", default=acc.get("self_mute", True))
                    new_deaf = Confirm.ask("Self Deafen?", default=acc.get("self_deaf", True))
                    new_pres = Prompt.ask("Status Presence", choices=["online", "idle", "dnd", "invisible"], default=acc.get("presence", "online"))

                    if not new_guild.isdigit() or not new_channel.isdigit():
                        console.print("[#DA373C]Server ID dan Channel ID harus berupa angka![/]")
                        time.sleep(1.5)
                        continue

                    acc["name"] = new_name
                    acc["token"] = new_token
                    acc["guild_id"] = new_guild
                    acc["channel_id"] = new_channel
                    acc["self_mute"] = new_mute
                    acc["self_deaf"] = new_deaf
                    acc["presence"] = new_pres
                    save_accounts(accounts)
                    console.print(f"[bold #23A55A]✓ Akun '{new_name}' berhasil diperbarui![/]")
                else:
                    console.print("[#DA373C]Nomor akun tidak valid.[/]")
            except ValueError:
                console.print("[#DA373C]Input harus berupa angka.[/]")
            time.sleep(1)

        elif action == "3":
            if not accounts:
                continue
            pick = Prompt.ask("Nomor akun yang ingin di-toggle", default="1")
            try:
                idx = int(pick) - 1
                if 0 <= idx < len(accounts):
                    accounts[idx]["enabled"] = not accounts[idx].get("enabled", True)
                    save_accounts(accounts)
                    st = "[bold #23A55A]ENABLED[/]" if accounts[idx]["enabled"] else "[bold #DA373C]DISABLED[/]"
                    console.print(f"[#FEE75C]Status akun '{accounts[idx]['name']}' sekarang: {st}[/]")
                else:
                    console.print("[#DA373C]Nomor akun tidak valid.[/]")
            except ValueError:
                console.print("[#DA373C]Input harus berupa angka.[/]")
            time.sleep(1)

        elif action == "4":
            if not accounts:
                continue
            pick = Prompt.ask("Nomor akun yang ingin diubah audio state", default="1")
            try:
                idx = int(pick) - 1
                if 0 <= idx < len(accounts):
                    acc = accounts[idx]
                    acc["self_mute"] = not acc.get("self_mute", True)
                    acc["self_deaf"] = not acc.get("self_deaf", True)
                    save_accounts(accounts)
                    m = "Muted" if acc["self_mute"] else "Open"
                    d = "Deaf" if acc["self_deaf"] else "Open"
                    console.print(f"[bold #23A55A]Audio akun '{acc['name']}' diubah -> Mic: {m} | Headphone: {d}[/]")
                else:
                    console.print("[#DA373C]Nomor akun tidak valid.[/]")
            except ValueError:
                console.print("[#DA373C]Input harus berupa angka.[/]")
            time.sleep(1)

        elif action == "5":
            if not accounts:
                continue
            pick = Prompt.ask("Nomor akun yang ingin diubah presence", default="1")
            try:
                idx = int(pick) - 1
                if 0 <= idx < len(accounts):
                    acc = accounts[idx]
                    new_pres = Prompt.ask("Pilih Status", choices=["online", "idle", "dnd", "invisible"], default="online")
                    acc["presence"] = new_pres
                    save_accounts(accounts)
                    console.print(f"[bold #23A55A]Presence akun '{acc['name']}' diubah menjadi: {new_pres.upper()}[/]")
                else:
                    console.print("[#DA373C]Nomor akun tidak valid.[/]")
            except ValueError:
                console.print("[#DA373C]Input harus berupa angka.[/]")
            time.sleep(1)

        elif action == "6":
            if not accounts:
                continue
            pick = Prompt.ask("Nomor akun yang ingin dihapus", default="1")
            try:
                idx = int(pick) - 1
                if 0 <= idx < len(accounts):
                    target = accounts[idx]
                    if Confirm.ask(f"Yakin ingin menghapus akun '{target['name']}'?", default=False):
                        accounts.pop(idx)
                        save_accounts(accounts)
                        console.print("[bold #DA373C]Akun berhasil dihapus.[/]")
                else:
                    console.print("[#DA373C]Nomor akun tidak valid.[/]")
            except ValueError:
                console.print("[#DA373C]Input harus berupa angka.[/]")
            time.sleep(1)

        elif action == "0":
            break


def global_settings_manager():
    settings = load_settings()
    while True:
        show_banner()
        console.print(Panel(
            "[bold white]GLOBAL ENGINE SETTINGS[/]\n"
            "[dim]Konfigurasi delay startup antar-akun dan auto-reconnect limit.[/dim]",
            border_style="#5865F2",
            title="[bold #5865F2]ENGINE CONFIG[/]",
            title_align="left",
        ))

        s_table = Table(border_style="#5865F2", header_style="bold #5865F2", title_justify="left")
        s_table.add_column("Setting", style="bold white")
        s_table.add_column("Nilai Saat Ini", style="#00F0FF")
        s_table.add_column("Deskripsi", style="dim")

        s_table.add_row(
            "1. Stagger Delay",
            f"{settings.get('stagger_delay', 2.0)} detik",
            "Jeda waktu connect antar-akun agar aman dari rate-limit"
        )
        s_table.add_row(
            "2. Max Reconnect",
            f"{settings.get('max_reconnect_attempts', 10)} kali",
            "Batas percobaan masuk ulang saat koneksi putus"
        )
        s_table.add_row(
            "3. Auto Wake-Lock",
            "Aktif" if settings.get("auto_wake_lock", True) else "Mati",
            "Cegah sleep mode di background Android Termux"
        )
        console.print(s_table)
        console.print("")

        console.print("[bold #5865F2][1][/] Ubah Stagger Delay")
        console.print("[bold #5865F2][2][/] Ubah Max Reconnect Attempts")
        console.print("[bold #5865F2][3][/] Toggle Auto Wake-Lock")
        console.print("[bold #5865F2][0][/] Kembali ke Menu Utama\n")

        pick = Prompt.ask("Pilih opsi", choices=["1", "2", "3", "0"], default="0")
        if pick == "1":
            val = Prompt.ask("Masukkan delay baru (detik)", default=str(settings.get("stagger_delay", 2.0)))
            try:
                settings["stagger_delay"] = max(0.5, float(val))
                save_settings(settings)
                console.print("[bold #23A55A]✓ Stagger delay diperbarui.[/]")
            except ValueError:
                console.print("[#DA373C]Nilai harus berupa angka.[/]")
            time.sleep(1)
        elif pick == "2":
            val = Prompt.ask("Masukkan batas reconnect", default=str(settings.get("max_reconnect_attempts", 10)))
            try:
                settings["max_reconnect_attempts"] = max(1, int(val))
                save_settings(settings)
                console.print("[bold #23A55A]✓ Max reconnect diperbarui.[/]")
            except ValueError:
                console.print("[#DA373C]Nilai harus berupa angka bulat.[/]")
            time.sleep(1)
        elif pick == "3":
            settings["auto_wake_lock"] = not settings.get("auto_wake_lock", True)
            save_settings(settings)
            st = "Aktif" if settings["auto_wake_lock"] else "Mati"
            console.print(f"[#FEE75C]Auto wake-lock sekarang: {st}[/]")
            time.sleep(1)
        elif pick == "0":
            break


def run_all_headless():
    accs = load_accounts()
    settings = load_settings()
    active_accs = [a for a in accs if a.get("enabled", True)]
    if not active_accs:
        console.print("[bold #DA373C][ERROR] File accounts.json kosong atau tidak ada akun aktif![/]")
        console.print("Jalankan [cyan]python run.py[/cyan] terlebih dahulu untuk menambahkan akun.")
        sys.exit(1)

    platform = detect_platform()
    log_event("SYS", "SYS", f"Platform Terdeteksi: {platform}")
    log_event("SYS", "SYS", f"Menjalankan {len(active_accs)} akun aktif di background VPS/Terminal...")

    try:
        asyncio.run(run_bots(active_accs, settings))
    except (KeyboardInterrupt, SystemExit):
        console.print("\n[bold #FEE75C][Shutdown] Bot dimatikan.[/]")


def main():
    args = sys.argv[1:]
    if "--run" in args or "-r" in args or "start" in args or not sys.stdin.isatty():
        run_all_headless()
        return

    if "--list" in args or "-l" in args:
        accs = load_accounts()
        show_accounts_table(accs)
        return

    if "--verify" in args or "-v" in args:
        run_account_verifier()
        return

    if "--help" in args or "-h" in args:
        console.print("[bold #5865F2]Discord Voice Stay Manager - CLI Usage:[/]")
        console.print("  python run.py          : Buka menu interaktif terminal")
        console.print("  python run.py --run    : Langsung jalankan bot di background (VPS systemd)")
        console.print("  python run.py --verify : Verifikasi token dan server ID langsung ke Discord API")
        console.print("  python run.py --list   : Tampilkan tabel daftar akun tersimpan")
        return

    settings = load_settings()

    while True:
        show_banner()
        platform = detect_platform()
        accounts = load_accounts()
        active_count = len([a for a in accounts if a.get("enabled", True)])

        console.print(f"[bold #5865F2]Platform:[/bold #5865F2] {platform}  [dim]•[/]  [bold #5865F2]Database:[/bold #5865F2] {ACCOUNTS_FILE}")
        console.print(f"[bold #5865F2]Akun:[/bold #5865F2] [bold white]{len(accounts)}[/] total  [dim]•[/]  [bold #23A55A]{active_count} aktif[/]  [dim]•[/]  [bold #DA373C]{len(accounts) - active_count} nonaktif[/]\n")

        console.print("[bold #5865F2]1.[/] Start Voice Stay (24/7 Run)")
        console.print("[bold #5865F2]2.[/] Account Management (Tambah, Edit, Toggle, Mute/Deaf, Presence)")
        console.print("[bold #5865F2]3.[/] Verify Accounts (Live Discord API Ping Check)")
        console.print("[bold #5865F2]4.[/] Global Engine Settings (Stagger Delay, Reconnect Limit)")
        console.print("[bold #5865F2]0.[/] Exit")

        try:
            choice = Prompt.ask("\nPilih menu", choices=["1", "2", "3", "4", "0"], default="1")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[#FEE75C]Sampai jumpa![/]")
            break

        if choice == "1":
            if not accounts:
                console.print("[bold #DA373C]Belum ada akun tersimpan! Tambahkan di Account Management (Menu 2).[/]")
                time.sleep(2)
                continue
            if active_count == 0:
                console.print("[bold #DA373C]Tidak ada akun yang aktif! Aktifkan di Account Management (Menu 2).[/]")
                time.sleep(2)
                continue
            try:
                asyncio.run(run_bots(accounts, settings))
            except (KeyboardInterrupt, SystemExit):
                pass
        elif choice == "2":
            account_manager()
        elif choice == "3":
            run_account_verifier()
        elif choice == "4":
            global_settings_manager()
        elif choice == "0":
            console.print("\n[#FEE75C]Sampai jumpa![/]")
            break


if __name__ == "__main__":
    main()
