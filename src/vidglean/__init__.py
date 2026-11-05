"""VidGlean：本地 AI 视频总结工具。"""

__version__ = "0.1.0"


def main() -> None:
    """控制台入口（``vidglean`` 命令）。"""
    from vidglean.app import cli

    cli()
