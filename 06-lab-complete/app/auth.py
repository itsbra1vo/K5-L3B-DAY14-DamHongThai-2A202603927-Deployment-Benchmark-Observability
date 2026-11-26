"""API key authentication dependency."""
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    if not settings.agent_api_key or not api_key or not secrets.compare_digest(api_key, settings.agent_api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key",
                            headers={"WWW-Authenticate": "ApiKey"})
    return api_key
