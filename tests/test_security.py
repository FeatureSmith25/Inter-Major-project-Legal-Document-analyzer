from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.security import current_user


def test_bearer_tokens_resolve_separate_document_owners(monkeypatch):
    monkeypatch.setattr("app.api.security.get_settings", lambda: SimpleNamespace(
        user_tokens_json='{"alpha-token":"user-a","beta-token":"user-b"}'
    ))
    assert current_user("Bearer alpha-token") == "user-a"
    assert current_user("Bearer beta-token") == "user-b"
    with pytest.raises(HTTPException) as error:
        current_user("Bearer invalid")
    assert error.value.status_code == 401


def test_local_mode_has_single_local_owner(monkeypatch):
    monkeypatch.setattr("app.api.security.get_settings", lambda: SimpleNamespace(user_tokens_json=""))
    assert current_user(None) == "local"


def test_api_hides_one_users_document_from_another(monkeypatch):
    import io
    from docx import Document
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setattr("app.api.security.get_settings", lambda: SimpleNamespace(
        user_tokens_json='{"owner-token":"owner-a","other-token":"owner-b"}'
    ))
    doc = Document()
    doc.add_paragraph("This agreement starts on January 1, 2025.")
    body = io.BytesIO()
    doc.save(body)
    with TestClient(app) as client:
        uploaded = client.post("/api/documents", headers={"Authorization": "Bearer owner-token"}, files={
            "file": ("private.docx", body.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        })
        assert uploaded.status_code == 201
        document_id = uploaded.json()["id"]
        assert client.get("/api/documents", headers={"Authorization": "Bearer other-token"}).json() == []
        assert client.get(f"/api/documents/{document_id}", headers={"Authorization": "Bearer other-token"}).status_code == 404
        assert client.delete(f"/api/documents/{document_id}", headers={"Authorization": "Bearer owner-token"}).status_code == 204
