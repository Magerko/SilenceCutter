# -*- mode: python ; coding: utf-8 -*-
import os

# ffmpeg is not kept in the repository. Put it in vendor/ before building (the
# release workflow downloads it); without it the app still builds and falls back
# to whatever is on PATH. ffprobe is deliberately not shipped - durations are
# parsed from ffmpeg's own output, which keeps ~100 MB out of the download.
binaries = []
candidate = os.path.join('vendor', 'ffmpeg.exe')
if os.path.exists(candidate):
    binaries.append((candidate, '.'))

datas = [('resources/icon.png', 'resources')]
for extra in ('vendor/FFMPEG-LICENSE.txt', 'vendor/FFMPEG-README.txt'):
    if os.path.exists(extra):
        datas.append((extra, '.'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'pydoc_data',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtQml',
        'PyQt6.QtQuick',
        'PyQt6.QtQuick3D',
        'PyQt6.QtMultimedia',
        'PyQt6.QtBluetooth',
        'PyQt6.QtNfc',
        'PyQt6.QtPositioning',
        'PyQt6.QtSensors',
        'PyQt6.QtSerialPort',
        'PyQt6.QtSql',
        'PyQt6.QtTest',
        'PyQt6.QtCharts',
        'PyQt6.QtDataVisualization',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SilenceCutter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX mangles Qt DLLs and is a reliable way to get flagged by antivirus.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SilenceCutter',
)
