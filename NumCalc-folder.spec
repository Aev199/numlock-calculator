# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app_keyboard.py'],
    pathex=[],
    binaries=[],
    datas=[('renderer', 'renderer')],
    hiddenimports=[
        'calc_engine_runtime',
        'pystray._win32',
        'PIL.Image',
        'PIL.ImageDraw',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NumCalc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    version='version_info.txt',
    manifest='NumCalc.manifest',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='NumCalc',
)
