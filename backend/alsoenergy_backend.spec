# PyInstaller spec for the AlsoEnergy migration tool backend.
# Build with: pyinstaller alsoenergy_backend.spec --noconfirm

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

# Bundle certifi's CA cert file so httpx can make HTTPS calls.
try:
    import certifi
    certifi_datas = [(certifi.where(), "certifi")]
except ImportError:
    certifi_datas = []

# collect_all picks up all keyring backends, data files, and hidden imports
# automatically — avoids having to manually list every pywin32 sub-module.
keyring_datas, keyring_binaries, keyring_hiddenimports = collect_all("keyring")

block_cipher = None

a = Analysis(
    ["run_backend.py"],
    pathex=[str(Path(".").resolve())],
    binaries=keyring_binaries,
    datas=certifi_datas + keyring_datas,
    hiddenimports=[
        # SQLModel / SQLAlchemy internals that PyInstaller misses
        "sqlmodel",
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.dialects.sqlite.pysqlite",
        "aiosqlite",
        # FastAPI / Starlette
        "fastapi",
        "starlette",
        "starlette.routing",
        "starlette.middleware",
        "sse_starlette",
        # Pydantic
        "pydantic",
        "pydantic_settings",
        "pydantic.deprecated.class_validators",
        # httpx + SSL
        "httpx",
        "certifi",
        "anyio",
        "anyio.backends.asyncio",
        "anyio._backends._asyncio",  # internal name in newer anyio
        # uvicorn internals
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # h11 — uvicorn's fallback HTTP/1.1 implementation
        "h11",
        # httptools — uvicorn's fast HTTP parser (available on Windows)
        "httptools",
        # dotenv
        "dotenv",
        # keyring — collect_all handles backends; explicit list is a safety net
        "keyring",
        "keyring.backends",
        "keyring.backends.macOS",
        "keyring.backends.SecretService",
        "keyring.backends.Windows",
        "keyring.backends.chainer",
        "keyring.backends.fail",
        "keyring.backends.null",
        # pywin32 modules required by keyring.backends.Windows
        "win32api",
        "win32con",
        "win32cred",
        "pywintypes",
    ] + keyring_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # uvloop is not available on Windows; exclude to prevent import errors
        "uvloop",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="alsoenergy-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
