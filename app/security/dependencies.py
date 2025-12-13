"""FastAPI dependencies for request authentication."""

from __future__ import annotations

import logging
import hmac
from datetime import datetime

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app import db_models
from app.config import settings
from app.db import get_db
from app.security.api_keys import (
    API_KEY_HEADER,
    ApiKeyPrincipal,
    hash_api_key,
    is_test_key,
    key_prefix,
)

logger = logging.getLogger("sentinelai.security")

api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


def _auth_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _check_pepper() -> str:
    if not settings.api_key_pepper:
        logger.error("API key pepper is not configured; rejecting request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "api_key_misconfigured", "message": "API key pepper is not configured"},
        )
    return settings.api_key_pepper


async def require_api_key(
    request: Request,
    api_key: str | None = Security(api_key_header),
    db: Session = Depends(get_db),
) -> ApiKeyPrincipal:
    """Authenticate requests using a hashed API key stored in the database."""

    if not settings.require_api_key:
        return ApiKeyPrincipal(email="dev-bypass", key_id="development", label="bypass")

    if not api_key or not api_key.strip():
        raise _auth_error(status.HTTP_401_UNAUTHORIZED, "api_key_missing", "API key header is required")

    provided_key = api_key.strip()

    if is_test_key(provided_key) and settings.sentinellai_env.lower() not in {"test", "testing"}:
        raise _auth_error(status.HTTP_403_FORBIDDEN, "api_key_test_only", "Test API keys are not accepted in this environment")

    stored = db.query(db_models.ApiKey).filter_by(key_prefix=key_prefix(provided_key)).first()
    if not stored:
        raise _auth_error(status.HTTP_401_UNAUTHORIZED, "api_key_invalid", "Invalid API key")

    if stored.revoked_at is not None:
        raise _auth_error(status.HTTP_403_FORBIDDEN, "api_key_revoked", "API key has been revoked")

    if stored.expires_at is not None and stored.expires_at <= datetime.utcnow():
        raise _auth_error(status.HTTP_403_FORBIDDEN, "api_key_expired", "API key has expired")

    pepper = _check_pepper()
    computed_hash = hash_api_key(provided_key, pepper)
    if not hmac.compare_digest(computed_hash, stored.key_hash):
        raise _auth_error(status.HTTP_401_UNAUTHORIZED, "api_key_invalid", "Invalid API key")

    try:  # best effort; do not block requests on telemetry updates
        stored.last_used_at = datetime.utcnow()
        stored.last_used_ip = request.client.host if request.client else None
        db.add(stored)
        db.commit()
    except Exception:  # pragma: no cover - fail soft
        db.rollback()
        logger.debug("Failed to update API key last-used metadata", exc_info=True)

    return ApiKeyPrincipal(email=stored.holder_email, key_id=str(stored.id), label=stored.holder_label)

