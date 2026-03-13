# -*- mode: python ; coding: utf-8 -*-
import os, imageio_ffmpeg

# Path to the bundled ffmpeg.exe that imageio-ffmpeg ships
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

block_cipher = None

a = Analysis(
    ['compressor.py'],
    pathex=[],
    binaries=[
        # Bundle the ffmpeg executable so video compression works offline
        (FFMPEG_EXE, 'imageio_ffmpeg/binaries'),
    ],
    datas=[
        # CustomTkinter assets (themes, fonts, images)
        (
            'C:\\Users\\david\\AppData\\Local\\Programs\\Python\\Python310\\lib\\site-packages\\customtkinter',
            'customtkinter'
        ),
        # tkinterdnd2 native libraries
        (
            'C:\\Users\\david\\AppData\\Local\\Programs\\Python\\Python310\\lib\\site-packages\\tkinterdnd2',
            'tkinterdnd2'
        ),
        # imageio-ffmpeg metadata (needed so the package finds its binary)
        (
            'C:\\Users\\david\\AppData\\Local\\Programs\\Python\\Python310\\lib\\site-packages\\imageio_ffmpeg',
            'imageio_ffmpeg'
        ),
    ],
    hiddenimports=[
        'customtkinter',
        'tkinterdnd2',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'imageio_ffmpeg',
        'ffmpeg',
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
    # icon='icon.ico',      # descomenta si tienes un .ico
)
