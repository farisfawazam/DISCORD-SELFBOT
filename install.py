import sys
import subprocess
import os

# ponytail: simple pip runner, upgrade to venv manager if isolation requested
def install_requirements():
    req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
    print(f"[*] Installing requirements from {req_file}...")
    cmd = [sys.executable, "-m", "pip", "install", "-r", req_file]
    res = subprocess.run(cmd)
    if res.returncode != 0:
        # Fallback untuk Debian 12 / Ubuntu 24.04 (PEP 668 externally-managed)
        cmd_fallback = cmd + ["--break-system-packages"]
        res = subprocess.run(cmd_fallback)
        if res.returncode != 0:
            print("[FAIL] Gagal menginstall dependencies.")
            sys.exit(res.returncode)

    print("[*] Memverifikasi dependensi...")
    import discord
    import aiohttp
    import rich
    import importlib.metadata
    print(f"[OK] discord.py-self ({getattr(discord, '__version__', 'ok')})")
    print(f"[OK] aiohttp ({aiohttp.__version__})")
    print(f"[OK] rich ({importlib.metadata.version('rich')})")
    print("\n[OK] Semua requirement selesai dipasang dan siap dijalankan.")

if __name__ == "__main__":
    install_requirements()
