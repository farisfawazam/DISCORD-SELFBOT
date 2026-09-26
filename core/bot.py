import sys
import os
import site

# Pastikan path user site-packages selalu terbaca
user_site = site.getusersitepackages()
if os.path.exists(user_site) and user_site not in sys.path:
    sys.path.insert(0, user_site)

# Pre-import nacl untuk memastikan library voice tersedia
try:
    import nacl
    import nacl.secret
    import nacl.utils
except ImportError:
    pass

import asyncio
import logging
import threading
from datetime import datetime
import discord
from discord.ext import commands

# Suppress internal discord logs
logging.getLogger("discord").setLevel(logging.WARNING)


class BotRunner:
    def __init__(self, account, on_log=None, on_status=None):
        self.account = account
        self.name = account["name"]
        self.on_log = on_log
        self.on_status = on_status
        self.bot = None
        self.loop = None
        self.thread = None
        self.running = False

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        text = f"[{ts}] [{self.name}] {msg}"
        if self.on_log:
            self.on_log(self.name, text)

    def set_status(self, status, detail=""):
        if self.on_status:
            self.on_status(self.name, status, detail)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.bot = commands.Bot(command_prefix="!", self_bot=True)
        token = self.account["token"]
        guild_id = int(self.account["guild_id"])
        channel_id = int(self.account["channel_id"])
        self_mute = self.account.get("self_mute", True)
        self_deaf = self.account.get("self_deaf", True)
        rc = 0

        @self.bot.event
        async def on_ready():
            nonlocal rc
            self.log(f"Login as {self.bot.user}")
            self.set_status("ONLINE", str(self.bot.user))

            guild = self.bot.get_guild(guild_id)
            if not guild:
                self.log("ERROR: Guild/Server ID not found")
                self.set_status("ERROR", "Server not found")
                await self.bot.close()
                return

            channel = guild.get_channel(channel_id)
            if not channel:
                self.log("ERROR: Voice Channel ID not found")
                self.set_status("ERROR", "Channel not found")
                await self.bot.close()
                return

            try:
                # 1. Connect ke voice
                vc = await channel.connect(self_mute=self_mute, self_deaf=self_deaf)

                # 2. Tunggu 1 detik agar gateway siap, lalu kirim update voice state untuk icon mute/deaf
                await asyncio.sleep(1)
                try:
                    await guild.change_voice_state(channel=channel, self_mute=self_mute, self_deaf=self_deaf)
                except Exception:
                    pass

                m_str = " [Muted]" if self_mute else ""
                d_str = " [Deafened]" if self_deaf else ""
                self.log(f"Connected to #{channel.name} @ {guild.name}{m_str}{d_str}")
                self.set_status("VOICE", f"#{channel.name}")
                rc = 0
            except Exception as e:
                self.log(f"Voice connect error: {e}")
                self.set_status("ERROR", str(e)[:30])
                await self.bot.close()

        @self.bot.event
        async def on_voice_state_update(member, before, after):
            nonlocal rc
            if member.id != self.bot.user.id:
                return
            if not (before.channel and not after.channel):
                return
            if not self.running:
                return

            rc += 1
            if rc > 10:
                self.log("Max reconnect limit reached. Stopping.")
                self.set_status("ERROR", "Max reconnect")
                await self.bot.close()
                return

            delay = min(5 * rc, 60)
            self.log(f"Disconnected. Reconnecting #{rc} in {delay}s...")
            self.set_status("RECONNECTING", f"#{rc} ({delay}s)")
            await asyncio.sleep(delay)

            guild = self.bot.get_guild(guild_id)
            channel = guild.get_channel(channel_id) if guild else None
            if channel and self.running:
                try:
                    await channel.connect(self_mute=self_mute, self_deaf=self_deaf)
                    await asyncio.sleep(1)
                    try:
                        await guild.change_voice_state(channel=channel, self_mute=self_mute, self_deaf=self_deaf)
                    except Exception:
                        pass
                    self.log(f"Reconnected to #{channel.name}")
                    self.set_status("VOICE", f"#{channel.name}")
                    rc = 0
                except Exception as e:
                    self.log(f"Reconnect failed: {e}")

        try:
            self.set_status("CONNECTING", "Starting...")
            self.log("Connecting to gateway...")
            self.bot.run(token, log_handler=None)
        except Exception as e:
            self.log(f"Fatal error: {e}")
            self.set_status("ERROR", str(e)[:30])
        finally:
            self.running = False
            self.set_status("OFFLINE", "")
            self.log("Stopped.")

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.log("Stopping bot...")

        if self.bot and self.loop and self.loop.is_running():
            async def _close():
                for vc in self.bot.voice_clients:
                    try:
                        await vc.disconnect(force=True)
                    except Exception:
                        pass
                await self.bot.close()
            asyncio.run_coroutine_threadsafe(_close(), self.loop)
