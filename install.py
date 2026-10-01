import sys
import subprocess
import os

# ponytail: auto-bootstraps pip via system package manager, upgrade to get-pip.py fallback if non-root container
def ensure_pip():
    res = subprocess.run([sys.executable, "-m", "pip", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if res.returncode == 0:
        return

    print("[*] pip belum terpasang di sistem. Mencoba auto-install...")
    is_root = getattr(os, "geteuid", lambda: 1)() == 0
    cmd_prefix = [] if is_root else ["sudo"]

    if os.path.exists("/usr/bin/apt-get"):
        subprocess.run(cmd_prefix + ["apt-get", "update", "-y"])
        subprocess.run(cmd_prefix + ["apt-get", "install", "-y", "python3-pip"])
    elif os.path.exists("/usr/bin/dnf"):
        subprocess.run(cmd_prefix + ["dnf", "install", "-y", "python3-pip"])
    else:
        subprocess.run([sys.executable, "-m", "ensurepip", "--default-pip"])

def install_requirements():
    ensure_pip()
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
