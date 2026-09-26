#!/bin/bash
# ============================================
#  Discord Selfbot - 1 Command Setup Termux
#  Copy paste SEMUA ini ke Termux, enter, done.
# ============================================
set -e
DIR=~/selfbot
mkdir -p $DIR && cd $DIR

# --- Install kalau belum ---
command -v python >/dev/null || { pkg update -y; pkg install python -y; }
pip install -q discord.py-self PyNaCl davey python-dotenv 2>/dev/null

# --- Cek saved token ---
if [ -f "$DIR/.env" ]; then
    source "$DIR/.env"
    echo ""
    echo "=============================="
    echo "  Token tersimpan ditemukan!"
    echo "  Token: ${DISCORD_TOKEN:0:8}...${DISCORD_TOKEN: -4}"
    echo "  Server: $GUILD_ID"
    echo "  Channel: $CHANNEL_ID"
    echo "=============================="
    echo ""
    read -p "Pakai token ini? (y/n): " USE_SAVED
    if [ "$USE_SAVED" != "n" ] && [ "$USE_SAVED" != "N" ]; then
        echo "[OK] Pakai token tersimpan."
    else
        rm "$DIR/.env"
        echo "[OK] Token lama dihapus. Input baru..."
    fi
fi

# --- Input kalau belum ada .env ---
if [ ! -f "$DIR/.env" ]; then
    echo ""
    echo "=============================="
    echo "  Setup Discord Selfbot"
    echo "=============================="
    echo ""
    echo "Cara dapet Token:"
    echo "  1. Buka Discord di browser HP"
    echo "  2. F12 / DevTools > Network"
    echo "  3. Kirim pesan, cari request"
    echo "  4. Header 'Authorization' = token"
    echo ""
    read -p "Paste Token Discord: " INPUT_TOKEN
    echo ""
    echo "Cara dapet ID: Settings > Advanced > Developer Mode ON"
    echo "  Klik tahan server/channel > Copy ID"
    echo ""
    read -p "Paste Server ID: " INPUT_GUILD
    read -p "Paste Voice Channel ID: " INPUT_CHANNEL

    cat > "$DIR/.env" << EOF
DISCORD_TOKEN=$INPUT_TOKEN
GUILD_ID=$INPUT_GUILD
CHANNEL_ID=$INPUT_CHANNEL
EOF
    echo ""
    echo "[OK] Token tersimpan di .env"
fi

# --- Generate Python files ---
cat > "$DIR/config.py" << 'PYEOF'
import os, sys
from dotenv import load_dotenv
load_dotenv()
def _req(k):
    v = os.getenv(k)
    if not v or v == "GANTI_INI":
        print(f"[ERROR] {k} belum diisi!"); sys.exit(1)
    return v
TOKEN = _req("DISCORD_TOKEN")
GUILD_ID = int(_req("GUILD_ID"))
CHANNEL_ID = int(_req("CHANNEL_ID"))
PYEOF

cat > "$DIR/stay_vc.py" << 'PYEOF'
import sys,os,signal,logging,asyncio,discord,config
from discord.ext import commands
logging.basicConfig(level=logging.INFO,format="[%(asctime)s] %(levelname)-7s %(message)s",datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout),logging.FileHandler("selfbot.log",encoding="utf-8")])
log=logging.getLogger("selfbot")
logging.getLogger("discord").setLevel(logging.WARNING)
bot=commands.Bot(command_prefix="!",self_bot=True)
rc=0
@bot.event
async def on_ready():
    log.info(f"Login: {bot.user}")
    g=bot.get_guild(config.GUILD_ID)
    if not g: log.error("Server not found");await bot.close();return
    ch=g.get_channel(config.CHANNEL_ID)
    if not ch: log.error("Channel not found");await bot.close();return
    try:
        await ch.connect()
        log.info(f"Voice: #{ch.name} @ {g.name}")
        log.info("Connected! Ctrl+C to stop.")
    except Exception as e: log.error(f"Voice fail: {e}");await bot.close()
@bot.event
async def on_voice_state_update(member,before,after):
    global rc
    if member.id!=bot.user.id or not(before.channel and not after.channel):return
    rc+=1
    if rc>10:log.error("Max reconnect");await bot.close();return
    d=min(5*rc,60);log.warning(f"DC. Reconnect #{rc} in {d}s...")
    await asyncio.sleep(d)
    g=bot.get_guild(config.GUILD_ID)
    ch=g.get_channel(config.CHANNEL_ID) if g else None
    if ch:
        try:await ch.connect();log.info("Reconnected");rc=0
        except Exception as e:log.error(f"Reconnect fail: {e}")
signal.signal(signal.SIGTERM,lambda*_:os._exit(0))
m=config.TOKEN[:8]+"..."+config.TOKEN[-4:]
log.info(f"Token: {m}")
bot.run(config.TOKEN,log_handler=None)
PYEOF

# --- Start ---
echo ""
echo "=============================="
echo "  Starting bot..."
echo "  Ctrl+C to stop"
echo "=============================="
echo ""
termux-wake-lock 2>/dev/null
cd $DIR && python stay_vc.py
