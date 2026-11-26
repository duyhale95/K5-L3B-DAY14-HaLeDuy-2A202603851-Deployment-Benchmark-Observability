import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis import RedisError

from utils.mock_llm import ask as llm_ask
from .auth import verify_api_key
from .cost_guard import check_budget, record_cost
from .rate_limiter import check_rate_limit
from .redis_client import r, redis_healthy

logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())
logger.propagate = False

def log(event: str, **fields):
    logger.info(json.dumps(dict(ts=datetime.now(timezone.utc).isoformat(), lvl="INFO", event=event, **fields)))

@asynccontextmanager
async def lifespan(app: FastAPI):
    log("startup")
    try:
        yield
    finally:
        r.close()
        log("shutdown")

app = FastAPI(title="Production AI Agent", lifespan=lifespan)

@app.middleware("http")
async def log_request(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    log("request", path=request.url.path, status=response.status_code, ms=round((time.monotonic()-start)*1000, 2))
    return response

@app.exception_handler(RedisError)
async def unavailable(request: Request, exc: RedisError):
    return JSONResponse({"detail": "Redis unavailable"}, status_code=503)

class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(503, "Redis unavailable")
    return {"ready": True}

@app.post("/ask")
def ask(body: AskRequest, key: str = Depends(verify_api_key)):
    check_rate_limit(key)
    check_budget()
    answer = llm_ask(body.question)
    record_cost(max(1, len(body.question)//4), max(1, len(answer)//4))
    result = {"question": body.question, "answer": answer}
    if body.session_id:
        session = "chat:" + body.session_id
        with r.pipeline() as pipe:
            pipe.rpush(session, json.dumps(result)).expire(session, 86400).execute()
    return result
