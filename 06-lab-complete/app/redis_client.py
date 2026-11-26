import redis
from .config import settings

r = redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2)

def redis_healthy() -> bool:
    try:
        return r.ping()
    except redis.RedisError:
        return False
