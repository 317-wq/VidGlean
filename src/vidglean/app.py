"""应用入口：桌面模式（pywebview）与开发服务器。"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import uuid

LOCK_PORT = 47821
_server = None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _acquire_single_instance() -> socket.socket | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", LOCK_PORT))
        sock.listen(1)
        return sock
    except OSError:
        sock.close()
        return None


def _wait_for_port(port: int, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            try:
                sock.connect(("127.0.0.1", port))
                return True
            except OSError:
                time.sleep(0.1)
    return False


def _run_uvicorn(host: str, port: int) -> None:
    global _server
    import uvicorn

    from vidglean.api.server import create_app

    config = uvicorn.Config(create_app(), host=host, port=port, log_level="warning")
    _server = uvicorn.Server(config)
    _server.run()


def serve(host: str = "127.0.0.1", port: int = 8765, token: str = "") -> None:
    if token:
        os.environ["VIDGLEAN_TOKEN"] = token
    _run_uvicorn(host, port)


def run_desktop() -> int:
    lock = _acquire_single_instance()
    if lock is None:
        print("VidGlean 已经在运行。")
        return 0
    try:
        import webview
    except ImportError:
        print("未安装 pywebview，无法启动桌面窗口。")
        print("开发模式请使用：vidglean --serve --port 8765")
        print("桌面模式请先安装：uv sync --extra desktop")
        return 1

    token = uuid.uuid4().hex
    os.environ["VIDGLEAN_TOKEN"] = token
    port = _free_port()
    thread = threading.Thread(target=_run_uvicorn, args=("127.0.0.1", port), daemon=True)
    thread.start()
    if not _wait_for_port(port):
        print("后端服务启动失败。")
        return 1

    webview.create_window(
        "VidGlean",
        f"http://127.0.0.1:{port}/?token={token}",
        width=1240,
        height=820,
        min_size=(960, 640),
    )
    webview.start()
    if _server is not None:
        _server.should_exit = True
    thread.join(timeout=5)
    return 0


def cli() -> None:
    parser = argparse.ArgumentParser(prog="vidglean", description="本地 AI 视频总结工具")
    parser.add_argument("--serve", action="store_true", help="以 HTTP 服务方式启动（开发用）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default="", help="访问令牌，留空表示不校验")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args()

    from vidglean import __version__

    if args.version:
        print(__version__)
        return
    if args.serve:
        serve(args.host, args.port, args.token)
        return
    sys.exit(run_desktop())
