import os
import sys
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val or val == "PASTE_TOKEN_LO_DISINI":
        print(f"[ERROR] {key} belum diisi di file .env!")
        sys.exit(1)
    return val


TOKEN = _require("DISCORD_TOKEN")
GUILD_ID = int(_require("GUILD_ID"))
CHANNEL_ID = int(_require("CHANNEL_ID"))
