# PyInstaller spec for the AlsoEnergy migration tool backend.
# Build with: pyinstaller alsoenergy_backend.spec --noconfirm
#
# Uses onedir mode (not onefile) — more reliable on Windows for complex
# dependency trees; avoids the slow temp-extraction step on every launch.

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

# Bundle certifi's CA cert file so httpx can make HTTPS calls in the frozen binary.
try:
    import certifi
    certifi_datas = [(certifi.where(), "certifi")]
except ImportError:
    certifi_datas = []

# collect_all gathers data files, binaries, AND hidden imports for each package,
# so nothing gets missed by PyInstaller's static analysis.
_packages = [
    "fastapi",
    "uvicorn",
    "starlette",
    "pydantic",
    "pydantic_settings",
    "anyio",
    "httpx",
    "sqlalchemy",
    "sqlmodel",
    "aiosqlite",
    "sse_starlette",
    "keyring",   # includes pywin32 DLLs on Windows via collect_all
]

all_datas, all_binaries, all_hiddenimports = [], [], []
for pkg in _packages:
    try:
        d, b, h = collect_all(pkg)
        all_datas += d
        all_binaries += b
        all_hiddenimports += h
    except Exception as e:
        print(f"WARNING: collect_all({pkg!r}) failed: {e}")

block_cipher = None

a = Analysis(
    ["run_backend.py"],
    pathex=[str(Path(".").resolve())],
    binaries=all_binaries,
    datas=certifi_datas + all_datas,
    hiddenimports=all_hiddenimports + [
        # Extras not covered by collect_all
        "certifi",
        "dotenv",
        "h11",
        "httptools",
        "win32api",
        "win32con",
        "win32cred",
        "pywintypes",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "uvloop",   # not available on Windows; excluding avoids import errors
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# onedir: EXE gets only scripts; binaries + datas go into COLLECT.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="alsoenergy-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="alsoenergy-backend",
)
