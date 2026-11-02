from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app as app_module
import database
import media

PNG = b"\x89PNG\r\n\x1a\nfake"


@pytest.fixture
def client(tmp_path, monkeypatch):
    database.configure_database(f"sqlite:///{tmp_path / 'media.db'}")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.delenv("WEBAPP_ENABLED", raising=False)
    art = tmp_path / "media"
    art.mkdir()
    (art / "pig-record.0123abcd.png").write_bytes(PNG)
    (art / "pig-record.png").write_bytes(PNG)
    (tmp_path / "app.py").write_text("secret", encoding="utf-8")
    monkeypatch.setattr(media, "MEDIA_DIR", art)
    with TestClient(app_module.app) as test_client:
        yield test_client


def test_media_serves_allowlisted_png(client):
    response = client.get("/media/pig-record.0123abcd.png")
    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


@pytest.mark.parametrize("name", [
    "..%2Fapp.py", "pig-record.png", "pig-other.0123abcd.png", "pig-record.0123ABCD.png", "x.svg",
    "pig-edit.0123abcd.png",
])
def test_media_rejects_other_names(client, name):
    assert client.get(f"/media/{name}").status_code == 404
