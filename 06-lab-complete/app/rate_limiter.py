from hashlib import sha256
from uuid import uuid4
from fastapi import HTTPException
from .config import settings
from .redis_client import r

# Redis time and a single script keep the sliding window consistent across workers.
admit = r.register_script("""
local now = redis.call('TIME')
local ms = now[1] * 1000 + math.floor(now[2] / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ms - 60000)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then return 0 end
redis.call('ZADD', KEYS[1], ms, ARGV[2])
redis.call('EXPIRE', KEYS[1], 60)
return 1
""")

def check_rate_limit(key: str) -> None:
    bucket = "rate:" + sha256(key.encode()).hexdigest()
    if not admit(keys=[bucket], args=[settings.rate_limit_per_minute, uuid4().hex]):
        raise HTTPException(429, "Too many requests")
