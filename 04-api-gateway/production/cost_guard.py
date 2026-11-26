"""Redis-backed monthly LLM budget guard.

Costs are stored as integer micro-dollars to avoid floating point drift. A
Lua script performs the budget check and reservation atomically across workers.
"""
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

import redis
from fastapi import HTTPException

logger = logging.getLogger(__name__)

PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006
MICRO_USD = 1_000_000

RESERVE_SCRIPT = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local amount = tonumber(ARGV[1])
local budget = tonumber(ARGV[2])
if current + amount > budget then return {0, current} end
local total = redis.call('INCRBY', KEYS[1], amount)
redis.call('EXPIRE', KEYS[1], ARGV[3])
return {1, total}
"""


@dataclass
class UsageRecord:
    user_id: str
    input_tokens: int
    output_tokens: int
    request_count: int
    month: str
    total_cost_usd: float


class CostGuard:
    def __init__(self, monthly_budget_usd: float = 10.0, redis_url: str | None = None):
        if monthly_budget_usd <= 0:
            raise ValueError("monthly_budget_usd must be positive")
        self.monthly_budget_usd = monthly_budget_usd
        self.redis = redis.Redis.from_url(
            redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )

    @staticmethod
    def _month() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    @staticmethod
    def _key(user_id: str, month: str) -> str:
        return f"cost-budget:{month}:{user_id}"

    @staticmethod
    def estimate_cost(input_tokens: int, output_tokens: int) -> float:
        return (input_tokens * PRICE_PER_1K_INPUT_TOKENS +
                output_tokens * PRICE_PER_1K_OUTPUT_TOKENS) / 1000

    def check_budget(self, user_id: str, estimated_cost: float = 0.0) -> None:
        """Atomically reserve estimated cost or return 402 when over budget."""
        if estimated_cost < 0:
            raise ValueError("estimated_cost cannot be negative")
        month = self._month()
        key = self._key(user_id, month)
        amount = round(estimated_cost * MICRO_USD)
        budget = round(self.monthly_budget_usd * MICRO_USD)
        # Keep the key through the next month so it remains inspectable at rollover.
        ttl = 62 * 24 * 60 * 60
        try:
            allowed, total = self.redis.eval(RESERVE_SCRIPT, 1, key, amount, budget, ttl)
        except redis.RedisError as exc:
            logger.exception("Redis unavailable while checking monthly budget")
            raise HTTPException(status_code=503, detail="Budget service temporarily unavailable") from exc
        if not int(allowed):
            raise HTTPException(status_code=402, detail={
                "error": "Monthly budget exceeded",
                "used_usd": int(total) / MICRO_USD,
                "budget_usd": self.monthly_budget_usd,
                "resets_at": "start of next UTC month",
            })

    def record_usage(self, user_id: str, input_tokens: int, output_tokens: int) -> UsageRecord:
        """Record usage after the LLM call; request estimate is reserved beforehand."""
        month = self._month()
        key = self._key(user_id, month)
        cost = self.estimate_cost(input_tokens, output_tokens)
        # Track token/request metrics separately from the budget counter.
        try:
            pipe = self.redis.pipeline()
            pipe.hincrby(f"cost-usage:{month}:{user_id}", "input_tokens", input_tokens)
            pipe.hincrby(f"cost-usage:{month}:{user_id}", "output_tokens", output_tokens)
            pipe.hincrby(f"cost-usage:{month}:{user_id}", "requests", 1)
            pipe.expire(f"cost-usage:{month}:{user_id}", 62 * 24 * 60 * 60)
            pipe.execute()
            # Reconcile conservative pre-call reservation with actual usage.
            # INCRBY supports negative deltas and preserves the atomic budget total.
            reserved = round(self.estimate_cost(input_tokens, 256) * MICRO_USD)
            actual = round(cost * MICRO_USD)
            if reserved != actual:
                self.redis.incrby(key, actual - reserved)
            total = int(self.redis.get(key) or 0) / MICRO_USD
            metrics = self.redis.hgetall(f"cost-usage:{month}:{user_id}")
        except redis.RedisError as exc:
            logger.exception("Redis unavailable while recording usage")
            raise HTTPException(status_code=503, detail="Usage service temporarily unavailable") from exc
        logger.info("Usage recorded: user=%s month=%s cost=$%.6f", user_id, month, cost)
        return UsageRecord(user_id, input_tokens, output_tokens,
                           int(metrics.get("requests", 0)), month, total)

    def get_usage(self, user_id: str) -> dict:
        month = self._month()
        key = self._key(user_id, month)
        try:
            spent = int(self.redis.get(key) or 0) / MICRO_USD
            metrics = self.redis.hgetall(f"cost-usage:{month}:{user_id}")
        except redis.RedisError as exc:
            logger.exception("Redis unavailable while reading usage")
            raise HTTPException(status_code=503, detail="Usage service temporarily unavailable") from exc
        return {
            "user_id": user_id,
            "month": month,
            "requests": int(metrics.get("requests", 0)),
            "input_tokens": int(metrics.get("input_tokens", 0)),
            "output_tokens": int(metrics.get("output_tokens", 0)),
            "cost_usd": round(spent, 6),
            "budget_usd": self.monthly_budget_usd,
            "budget_remaining_usd": round(max(0, self.monthly_budget_usd - spent), 6),
            "budget_used_pct": round(spent / self.monthly_budget_usd * 100, 1),
        }


cost_guard = CostGuard(monthly_budget_usd=float(os.getenv("MONTHLY_USER_BUDGET_USD", "10")))
