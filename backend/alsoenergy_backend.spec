# PyInstaller spec for the AlsoEnergy migration tool backend.
# Build with: .venv/bin/pyinstaller alsoenergy_backend.spec

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['run_backend.py'],
    pathex=[str(Path('.').resolve())],
    binaries=[],
    datas=[],
    hiddenimports=[
        # SQLModel / SQLAlchemy internals that PyInstaller misses
        'sqlmodel',
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.dialects.sqlite.pysqlite',
        'aiosqlite',
        # FastAPI / Starlette
        'fastapi',
        'starlette',
        'starlette.routing',
        'starlette.middleware',
        'sse_starlette',
        # Pydantic
        'pydantic',
        'pydantic_settings',
        'pydantic.deprecated.class_validators',
        # httpx
        'httpx',
        'anyio',
        'anyio.backends.asyncio',
        # uvicorn internals
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # dotenv
        'dotenv',
        # keyring — OS secure credential store
        'keyring',
        'keyring.backends',
        'keyring.backends.macOS',
        'keyring.backends.SecretService',
        'keyring.backends.Windows',
        'keyring.backends.fail',
        'keyring.backends.null',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='alsoenergy-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # Keep console for now so we can see output during testing
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
