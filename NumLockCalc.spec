# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

webview_datas = collect_data_files('webview')


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('renderer', 'renderer'), *webview_datas],
    hiddenimports=['clr', 'webview.platforms.winforms'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['cefpython3', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'gi'],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='NumLockCalc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
