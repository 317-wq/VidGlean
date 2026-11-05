# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（Windows）。

用法（仓库根目录）：
    pyinstaller packaging/vidglean.spec --noconfirm
产物：dist/VidGlean/VidGlean.exe
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

datas = [
    (str(ROOT / "src" / "vidglean" / "web"), "vidglean/web"),
]

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("bilibili_api")
    + [
        "vidglean.app",
        "vidglean.api.server",
        "encodings.idna",
    ]
)

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest", "IPython"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VidGlean",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="VidGlean",
)
