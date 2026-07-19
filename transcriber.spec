# -*- mode: python ; coding: utf-8 -*-
"""Отдельный исполняемый файл распознавания речи.

Qt6 и ctranslate2 конфликтуют при загрузке нативных библиотек. Запуска в
отдельном процессе недостаточно, если это один и тот же exe: у собранного
приложения обе библиотеки лежат в одной папке _internal, Windows подтягивает
их в оба процесса, и падение возвращается.

Поэтому распознавание — самостоятельный файл со своим _internal, где Qt нет
вовсе. Основное приложение при этом становится заметно легче: весь стек
whisper живёт только здесь.
"""
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for package in ('faster_whisper', 'ctranslate2', 'onnxruntime', 'tokenizers',
                'av', 'huggingface_hub'):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    ['core/transcribe_cli.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Ради чего всё и затевалось: здесь Qt быть не должно.
        'PyQt6',
        'PyQt5',
        'tkinter',
        'unittest',
        'pydoc_data',
        'torch',
        'matplotlib',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='sc-transcribe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # Консольный: родитель читает его вывод, окна он не показывает.
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='transcriber',
)
