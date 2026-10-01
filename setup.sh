#!/data/data/com.termux/files/usr/bin/bash
# ========================================================
# Setup 1x Discord Voice Stay (Curl-CFFI Full Protocol Mock)
# ========================================================
set -e

echo "=========================================="
echo "  [1/3] Menyiapkan Python Dasar..."
echo "=========================================="
pkg update -y
pkg install -y python git

echo "=========================================="
echo "  [2/3] Memasang Library Python & Davey..."
echo "=========================================="
SITE_DIR=$(python3 -c "import site; print(site.getsitepackages()[0])")

python3 -c "
import urllib.request, json, zipfile, io, sys, sysconfig, shutil, os

paths = [sysconfig.get_path('purelib'), sysconfig.get_path('platlib')]
for p in sys.path:
    if 'site-packages' in p and p not in paths:
        paths.append(p)

headers = {'User-Agent': 'pip/24.0 (Termux AutoInstaller)'}

for p in paths:
    for folder in ['curl_cffi', 'audioop', 'cffi']:
        target_dir = os.path.join(p, folder)
        if os.path.exists(target_dir):
            if os.path.isdir(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            else:
                os.remove(target_dir)

def get_wheel_url(pkg_name, preferred_tag=None):
    api_url = f'https://pypi.org/pypi/{pkg_name}/json'
    req = urllib.request.Request(api_url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    
    urls = data.get('urls', [])
    if preferred_tag:
        for u in urls:
            fn = u.get('filename', '')
            if fn.endswith('.whl') and preferred_tag in fn:
                return u.get('url'), fn
    for u in urls:
        fn = u.get('filename', '')
        if fn.endswith('.whl') and ('py3-none-any' in fn or 'py2.py3-none-any' in fn):
            return u.get('url'), fn
    for u in urls:
        fn = u.get('filename', '')
        if fn.endswith('.whl'):
            return u.get('url'), fn
    return None, None

packages = [
    'blinker', 'click', 'itsdangerous', 'werkzeug', 'jinja2', 'markupsafe', 'flask', 'python-dotenv',
    'typing_extensions', 'attrs', 'idna', 'multidict', 'propcache', 'yarl',
    'frozenlist', 'aiosignal', 'aiohappyeyeballs', 'async-timeout', 'aiohttp',
    'certifi', 'protobuf', 'tzlocal', 'tzdata', 'discord_protos',
    'discord.py-self'
]

print('Mengekstrak paket dasar...')
for pkg in packages:
    try:
        url, fn = get_wheel_url(pkg)
        if not url:
            continue
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
        z = zipfile.ZipFile(io.BytesIO(content))
        for p in paths:
            z.extractall(p)
        print(f'  [OK] {pkg}')
    except Exception as e:
        print(f'  [FAIL] {pkg}: {e}')

print('\nMemasang binary davey...')
try:
    v = f'{sys.version_info.major}{sys.version_info.minor}'
    url, fn = get_wheel_url('davey', preferred_tag=f'cp{v}')
    if not url:
        url, fn = get_wheel_url('davey', preferred_tag='aarch64')
    if url:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
        z = zipfile.ZipFile(io.BytesIO(content))
        for p in paths:
            z.extractall(p)
        print(f'  [OK] davey ({fn})')
except Exception as e:
    print(f'  [FAIL] davey: {e}')

# Pasang curl_cffi mock yang lengkap dengan atext & ajson & RequestsError
init_code = '''class CurlError(Exception): pass
class WebSocketError(Exception): pass
class CurlMime:
    def addpart(self, *a, **k): pass

from . import requests
from . import const

__all__ = ['CurlError', 'WebSocketError', 'CurlMime', 'requests', 'const']
'''

requests_code = '''import aiohttp
import asyncio
import json

class RequestsError(Exception): pass
class CurlError(Exception): pass

class impersonate:
    DEFAULT_CHROME = 'chrome'

class session:
    class HttpMethod: pass

class Response:
    def __init__(self, status, headers, content):
        self.status_code = status
        self.status = status
        self.headers = headers
        self.content = content
        self.text = content.decode('utf-8', errors='replace')
    def json(self):
        return json.loads(self.text)
    async def atext(self):
        return self.text
    async def ajson(self):
        return self.json()

class AsyncSession:
    def __init__(self, *args, **kwargs):
        self._session = None

    async def _get_session(self):
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def request(self, method, url, headers=None, data=None, json=None, params=None, **kwargs):
        sess = await self._get_session()
        kwargs.pop('impersonate', None)
        kwargs.pop('timeout', None)
        async with sess.request(method, url, headers=headers, data=data, json=json, params=params) as resp:
            content = await resp.read()
            return Response(resp.status, resp.headers, content)

    async def ws_connect(self, url, **kwargs):
        sess = await self._get_session()
        kwargs.pop('impersonate', None)
        headers = kwargs.pop('headers', {})
        return await sess.ws_connect(url, headers=headers)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

class Session(AsyncSession): pass
class AsyncWebSocket: pass
'''

const_code = '''class CurlWsFlag:
    TEXT = 1
    BINARY = 2
    CLOSE = 8
'''

for p in paths:
    c_pkg = os.path.join(p, 'curl_cffi')
    os.makedirs(c_pkg, exist_ok=True)
    with open(os.path.join(c_pkg, '__init__.py'), 'w', encoding='utf-8') as f:
        f.write(init_code)
    with open(os.path.join(c_pkg, 'requests.py'), 'w', encoding='utf-8') as f:
        f.write(requests_code)
    with open(os.path.join(c_pkg, 'const.py'), 'w', encoding='utf-8') as f:
        f.write(const_code)

    with open(os.path.join(p, 'audioop.py'), 'w', encoding='utf-8') as f:
        f.write('error = Exception\\ndef getsample(*a,**k): return 0\\n')
"

echo "=========================================="
echo "  [3/3] Memverifikasi Status Akhir..."
echo "=========================================="
python3 -c "import flask; print('  [OK] Flask Ready!')"
python3 -c "import discord; print('  [OK] Discord.py-self Ready!')"
python3 -c "import davey; print('  [OK] Davey Protocol Versi:', davey.DAVE_PROTOCOL_VERSION)" 2>/dev/null || true

echo ""
echo "=========================================="
echo "  SETUP SELESAI 100%!"
echo "  Jalankan sekarang:"
echo "  python run.py"
echo "=========================================="
