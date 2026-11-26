"""Redis-backed, per-API-key sliding-window rate limiter."""
import time

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import r

_WINDOW_MS = 60_000
_LIMIT_SCRIPT = r.register_script("""
local key = KEYS[1]
local now = tonumber(ARGV[1])
local cutoff = now - tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
local count = redis.call('ZCARD', key)
if count >= limit then
  local first = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local retry = 1
  if first[2] then retry = math.max(1, math.ceil((tonumber(first[2]) + tonumber(ARGV[2]) - now) / 1000)) end
  return {0, retry}
end
redis.call('ZADD', key, now, ARGV[4])
redis.call('PEXPIRE', key, tonumber(ARGV[2]))
return {1, 0}
""")


def check_rate_limit(key: str) -> None:
    now_ms = int(time.time() * 1000)
    try:
        allowed, retry_after = _LIMIT_SCRIPT(
            keys=[f"rate-limit:{key}"], args=[now_ms, _WINDOW_MS,
                                                max(1, settings.rate_limit_per_minute),
                                                f"{now_ms}:{time.time_ns()}"])
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable") from exc
    if int(allowed) != 1:
        raise HTTPException(status_code=429, detail="Rate limit exceeded",
                            headers={"Retry-After": str(int(retry_after))})
