"""Monthly token cost accounting, shared across workers through Redis."""
from datetime import datetime, timezone

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _month_key() -> str:
    now = datetime.now(timezone.utc)
    return f"llm-cost:{now:%Y-%m}"


def check_budget() -> None:
    try:
        spent = float(r.get(_month_key()) or 0)
    except (RedisError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Cost guard unavailable") from exc
    if spent >= settings.monthly_budget_usd:
        raise HTTPException(status_code=402, detail="Monthly budget exceeded")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    cost = max(0, input_tokens) / 1000 * PRICE_INPUT_PER_1K + max(0, output_tokens) / 1000 * PRICE_OUTPUT_PER_1K
    try:
        pipe = r.pipeline()
        pipe.incrbyfloat(_month_key(), cost)
        pipe.expire(_month_key(), 60 * 60 * 24 * 40)
        pipe.execute()
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Cost accounting unavailable") from exc
    return cost
