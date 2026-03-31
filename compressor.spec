# -*- mode: python ; coding: utf-8 -*-
import os, imageio_ffmpeg
import sys
from pathlib import Path

# Path to the bundled ffmpeg.exe that imageio-ffmpeg ships
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

# Find pngquant.exe
def _find_pngquant():
    import shutil
    found = shutil.which("pngquant")
    if found:
        return found
    for candidate in [
        Path(sys.executable).parent / "Scripts" / "pngquant.exe",
        Path(sys.executable).parent / "pngquant.exe",
    ]:
        if candidate.exists():
            return str(candidate)
    return None

PNGQUANT_EXE = _find_pngquant()

# Dynamically resolve site-packages for the current Python install
SITE_PACKAGES = Path(sys.executable).parent / "Lib" / "site-packages"

block_cipher = None

a = Analysis(
    ['compressor.py'],
    pathex=[],
    binaries=[
        # Bundle the ffmpeg executable so video compression works offline
        (FFMPEG_EXE, 'imageio_ffmpeg/binaries'),
    ] + ([(PNGQUANT_EXE, '.')] if PNGQUANT_EXE else []),
    datas=[
        # CustomTkinter assets (themes, fonts, images)
        (str(SITE_PACKAGES / 'customtkinter'), 'customtkinter'),
        # tkinterdnd2 native libraries
        (str(SITE_PACKAGES / 'tkinterdnd2'), 'tkinterdnd2'),
        # imageio-ffmpeg metadata (needed so the package finds its binary)
        (str(SITE_PACKAGES / 'imageio_ffmpeg'), 'imageio_ffmpeg'),
        ('favicon.ico', '.'),
    ],
    hiddenimports=[
        'customtkinter',
        'tkinterdnd2',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'imageio_ffmpeg',
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
    a.datas,
    [],
    name='Compresso',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # sin consola negra
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='favicon.ico',
)
