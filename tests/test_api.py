"""HTTP 接口测试。"""

from __future__ import annotations

from vidglean import config
from vidglean.api.common import ok  # noqa: F401  (确保模块可导入)
from vidglean.store import repo


def _create_document(body: str = "# 标题\n\n内容关于并发编程与网络") -> str:
    doc_id = repo.create_document(
        platform="bilibili",
        video_id="BV1xx411c7mD",
        title="并发编程入门",
        author="测试UP",
        duration=600,
        source_url="https://www.bilibili.com/video/BV1xx411c7mD",
        content_type="技术教程",
        summary_depth="standard",
        file_path="",
    )
    path = config.documents_dir() / f"{doc_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, "utf-8")
    repo.update_document(doc_id, file_path=str(path), file_mtime=path.stat().st_mtime)
    repo.index_document(doc_id, "并发编程入门", body, ["并发", "网络"])
    return doc_id


def test_health(client):
    response = client.get("/api/health")
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["version"]
    assert payload["data"]["has_model"] is False


def test_settings_roundtrip(client):
    response = client.put("/api/settings", json={"values": {"theme": "dark", "max_retries": 5}})
    assert response.status_code == 200
    data = client.get("/api/settings").json()["data"]
    assert data["theme"] == "dark"
    assert data["max_retries"] == 5
    assert data["concurrency_video"] == 2


def test_documents_crud(client):
    doc_id = _create_document()
    listing = client.get("/api/documents").json()["data"]
    assert listing["total"] == 1
    assert listing["items"][0]["title"] == "并发编程入门"

    detail = client.get(f"/api/documents/{doc_id}").json()["data"]
    assert "并发编程" in detail["content"]
    assert "<h1" in detail["html"]

    patched = client.patch(f"/api/documents/{doc_id}", json={"starred": True, "tags": ["并发"]})
    assert patched.status_code == 200
    assert client.get("/api/documents?starred=true").json()["data"]["total"] == 1
    assert client.get("/api/documents?tag=并发").json()["data"]["total"] == 1
    assert client.get(f"/api/documents/{doc_id}").json()["data"]["tags"] == ["并发"]

    saved = client.put(f"/api/documents/{doc_id}/content", json={"content": "# 新标题\n\n改写"})
    assert saved.status_code == 200
    assert "改写" in (config.documents_dir() / f"{doc_id}.md").read_text("utf-8")

    assert client.delete(f"/api/documents/{doc_id}").status_code == 200
    assert client.get("/api/documents").json()["data"]["total"] == 0


def test_search_chinese(client):
    _create_document()
    assert client.get("/api/documents?q=并发").json()["data"]["total"] == 1
    assert client.get("/api/documents?q=编程").json()["data"]["total"] == 1
    assert client.get("/api/documents?q=区块链").json()["data"]["total"] == 0


def test_categories_and_tags(client):
    category = client.post("/api/categories", json={"name": "技术"}).json()["data"]
    doc_id = _create_document()
    client.patch(f"/api/documents/{doc_id}", json={"categories": [category["id"]]})
    assert client.get(f"/api/documents?category={category['id']}").json()["data"]["total"] == 1
    assert client.get("/api/categories").json()["data"]["items"][0]["count"] == 1
    client.delete(f"/api/categories/{category['id']}")
    assert client.get("/api/documents").json()["data"]["total"] == 1


def test_templates_seeded(client):
    items = client.get("/api/templates").json()["data"]["items"]
    assert len(items) >= 3
    assert all("variables" in item for item in items)


def test_upload_template(client):
    response = client.post(
        "/api/templates",
        json={"name": "自定义模板", "description": "测试", "content": "# {{video_title}}\n\n## 概述\n{{extra}}"},
    )
    assert response.status_code == 200
    bad = client.post(
        "/api/templates",
        json={"name": "坏模板", "description": "", "content": "# {{unknown_var}}"},
    )
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "BAD_TEMPLATE"


def test_model_crud(client):
    created = client.post(
        "/api/models",
        json={
            "name": "测试模型",
            "base_url": "https://example.com/v1",
            "model": "test-model",
            "api_key": "sk-test",
        },
    )
    assert created.status_code == 200
    model = created.json()["data"]
    assert model["has_key"] is True
    assert client.get("/api/models").json()["data"]["items"][0]["is_current"] == 1
    client.delete(f"/api/models/{model['id']}")
    assert client.get("/api/models").json()["data"]["items"] == []


def test_chat_requires_model(client):
    doc_id = _create_document()
    response = client.post(f"/api/documents/{doc_id}/chat", json={"message": "你好"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "API_KEY_INVALID"


def test_backup_and_restore(client):
    doc_id = _create_document("# 版本一")
    backup = client.post("/api/backup", json={"path": ""}).json()["data"]
    assert backup["encrypted"] is False
    client.put(f"/api/documents/{doc_id}/content", json={"content": "# 版本二"})
    restored = client.post("/api/restore", json={"path": backup["path"], "password": ""})
    assert restored.status_code == 200
    detail = client.get(f"/api/documents/{doc_id}").json()["data"]
    assert "版本一" in detail["content"]


def test_encrypted_backup_requires_password(client):
    _create_document()
    backup = client.post("/api/backup", json={"path": "", "password": "pw"}).json()["data"]
    assert backup["encrypted"] is True
    missing = client.post("/api/restore", json={"path": backup["path"], "password": ""})
    assert missing.status_code == 400
    wrong = client.post("/api/restore", json={"path": backup["path"], "password": "bad"})
    assert wrong.status_code == 400
    ok_response = client.post("/api/restore", json={"path": backup["path"], "password": "pw"})
    assert ok_response.status_code == 200


def test_cleanup(client):
    _create_document()
    response = client.post("/api/system/cleanup")
    assert response.json()["ok"] is True
