import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture()
def env(tmp_path, monkeypatch):
    home = tmp_path / "data"
    monkeypatch.setenv("VIDGLEAN_HOME", str(home))
    monkeypatch.setenv("VIDGLEAN_SECRETS", "file")
    from vidglean.store import db

    db.close_db()
    home.mkdir(parents=True, exist_ok=True)
    yield home
    db.close_db()


@pytest.fixture()
def client(env):
    from fastapi.testclient import TestClient

    from vidglean.api.server import create_app

    application = create_app()
    with TestClient(application) as test_client:
        yield test_client
