from datetime import datetime, timezone
from fastapi import HTTPException
from .config import settings
from .redis_client import r

def daily_key() -> str:
    return "cost:" + datetime.now(timezone.utc).date().isoformat()

def check_budget() -> None:
    if float(r.get(daily_key()) or 0) >= settings.daily_budget_usd:
        raise HTTPException(402, "Daily budget exhausted")

def record_cost(input_tokens: int, output_tokens: int) -> float:
    cost = (input_tokens * 0.00015 + output_tokens * 0.0006) / 1000
    key = daily_key()
    with r.pipeline() as pipe:
        pipe.incrbyfloat(key, cost).expire(key, 172800).execute()
    return cost
