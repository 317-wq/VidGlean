"""PyInstaller 入口。

打包成无控制台的 exe 后，启动阶段的异常必须自己接住并落盘，否则用户只会看到
窗口一闪而过。
"""

from __future__ import annotations

import traceback
from pathlib import Path


def _report(message: str) -> None:
    try:
        log_dir = Path.home() / "AppData" / "Local" / "VidGlean" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "startup-error.log").write_text(message, "utf-8")
    except Exception:
        pass
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message[:900], "VidGlean 启动失败", 0x10)
    except Exception:
        pass


def main() -> None:
    try:
        from vidglean.app import cli

        cli()
    except SystemExit:
        raise
    except Exception:
        _report(traceback.format_exc())


if __name__ == "__main__":
    main()
