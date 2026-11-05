# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（Windows）。

用法（仓库根目录，先装好 desktop + build 两组依赖）：
    uv sync --extra desktop --extra build
    uv run pyinstaller packaging/vidglean.spec --noconfirm
产物：dist/VidGlean/VidGlean.exe
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

datas = [
    (str(ROOT / "src" / "vidglean" / "web"), "vidglean/web"),
]
# httpx 走 HTTPS 需要根证书
datas += collect_data_files("certifi")

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("bilibili_api")
    + collect_submodules("vidglean")
    + [
        # 桌面壳：app.py 里是延迟导入，静态分析看不到
        "webview",
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
        "webview.util",
        "clr",
        "clr_loader",
        "pythonnet",
        # 凭证与回收站
        "keyring.backends.Windows",
        "win32ctypes.pywin32",
        # 其他
        "encodings.idna",
        "send2trash",
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
    icon=str(ROOT / "packaging" / "vidglean.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="VidGlean",
)
