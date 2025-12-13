from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal, init_db
from app.db_models import ApiKey
from app.main import app
from app.security import API_KEY_HEADER
from app.security.api_keys import generate_api_key, hash_api_key, key_prefix


@pytest.fixture
def auth_context(monkeypatch):
    monkeypatch.setattr(settings, "sentinellai_env", "test")
    monkeypatch.setattr(settings, "require_api_key", True)
    monkeypatch.setattr(settings, "api_key_pepper", "test-pepper-value")

    init_db()
    db = SessionLocal()
    db.query(ApiKey).delete()

    plaintext_key = generate_api_key(prefix="sk_test_sentinel")
    record = ApiKey(
        key_prefix=key_prefix(plaintext_key),
        key_hash=hash_api_key(plaintext_key, settings.api_key_pepper),
        holder_email="tester@example.com",
        holder_label="unit-test",
        created_at=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    client = TestClient(app)
    try:
        yield {"client": client, "key": plaintext_key, "db": db, "record": record}
    finally:
        client.close()
        db.query(ApiKey).delete()
        db.commit()
        db.close()


def test_missing_key_is_rejected(auth_context):
    response = auth_context["client"].get("/api/v1/analysis/status")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "api_key_missing"


def test_invalid_key_is_rejected(auth_context):
    response = auth_context["client"].get(
        "/api/v1/analysis/status", headers={API_KEY_HEADER: "sk_sentinel_invalid"}
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "api_key_invalid"


def test_revoked_key_is_blocked(auth_context):
    record = auth_context["db"].get(ApiKey, auth_context["record"].id)
    record.revoked_at = datetime.utcnow()
    auth_context["db"].commit()

    response = auth_context["client"].get(
        "/api/v1/analysis/status", headers={API_KEY_HEADER: auth_context["key"]}
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "api_key_revoked"


def test_expired_key_is_blocked(auth_context):
    record = auth_context["db"].get(ApiKey, auth_context["record"].id)
    record.expires_at = datetime.utcnow() - timedelta(seconds=1)
    auth_context["db"].commit()

    response = auth_context["client"].get(
        "/api/v1/analysis/status", headers={API_KEY_HEADER: auth_context["key"]}
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "api_key_expired"


def test_valid_key_allows_access(auth_context):
    response = auth_context["client"].get(
        "/api/v1/analysis/status", headers={API_KEY_HEADER: auth_context["key"]}
    )

    assert response.status_code == 200


def test_test_keys_blocked_in_prod(monkeypatch, auth_context):
    monkeypatch.setattr(settings, "sentinellai_env", "prod")

    response = auth_context["client"].get(
        "/api/v1/analysis/status", headers={API_KEY_HEADER: auth_context["key"]}
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "api_key_test_only"
