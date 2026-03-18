# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

a = Analysis(
    ['gui_launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('pictures',    'pictures'),
        ('audio',       'audio'),
        ('themes',      'themes'),
        ('config',      'config'),
        ('profiles',    'profiles'),
        ('version.json', '.'),
        ('app_icon.ico', '.'),
        ('Help.txt',    '.'),
    ],
    hiddenimports=[
        'interception',
        'interception._ioctl',
        'interception._keycodes',
        'interception._utils',
        'interception.beziercurve',
        'interception.constants',
        'interception.device',
        'interception.exceptions',
        'interception.inputs',
        'interception.interception',
        'interception.strokes',
        'pathgenerator',
        'cv2',
        'numpy',
        'mss',
        'mss.windows',
        'PIL',
        'PIL._tkinter_finder',
        'customtkinter',
        'keyboard',
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'multiprocessing',
        'multiprocessing.pool',
        'multiprocessing.managers',
        'pkg_resources.py2_warn',
        'requests',
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
    [],
    exclude_binaries=True,
    name='WorkerBee',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WorkerBee',
)
