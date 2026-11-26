from secrets import compare_digest
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from .config import settings

header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(key: str | None = Security(header)) -> str:
    if not key or not compare_digest(key.encode(), settings.agent_api_key.encode()):
        raise HTTPException(401, "Invalid API key")
    return key
