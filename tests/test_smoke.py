"""冒烟测试：确认包结构、入口和依赖都能正常导入。"""

import vidglean


def test_version() -> None:
    assert vidglean.__version__ == "0.1.0"


def test_entrypoint() -> None:
    assert callable(vidglean.main)


def test_core_deps_importable() -> None:
    import bilibili_api  # noqa: F401
    import fastapi  # noqa: F401
    import keyring  # noqa: F401
    import openai  # noqa: F401
