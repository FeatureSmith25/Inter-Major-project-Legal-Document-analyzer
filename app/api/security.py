import json
import secrets

from fastapi import Header, HTTPException

from app.config import get_settings


def current_user(authorization: str | None = Header(default=None)) -> str:
    """Resolve the document owner from a configured bearer token.

    With no token map configured, the app runs in local single-user mode.
    """
    configured = get_settings().user_tokens_json
    if not configured:
        return "local"
    try:
        token_owners = json.loads(configured)
    except json.JSONDecodeError as exc:
        raise HTTPException(500, "USER_TOKENS_JSON is not valid JSON.") from exc
    if not isinstance(token_owners, dict):
        raise HTTPException(500, "USER_TOKENS_JSON must map access tokens to user IDs.")
    if not token_owners:
        return "local"
    scheme, _, provided = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not provided:
        raise HTTPException(401, "A valid bearer token is required.", headers={"WWW-Authenticate": "Bearer"})
    for token, owner_id in token_owners.items():
        if isinstance(token, str) and secrets.compare_digest(token, provided):
            if isinstance(owner_id, str) and 1 <= len(owner_id) <= 128:
                return owner_id
    raise HTTPException(401, "A valid bearer token is required.", headers={"WWW-Authenticate": "Bearer"})
