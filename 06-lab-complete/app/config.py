"""Application settings loaded from the process environment."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    port: int = int(os.getenv("PORT", "8000"))
    environment: str = os.getenv("ENVIRONMENT", "development")
    agent_api_key: str = os.getenv("AGENT_API_KEY", "")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    monthly_budget_usd: float = float(os.getenv("MONTHLY_BUDGET_USD", os.getenv("DAILY_BUDGET_USD", "10")))
    # Kept for compatibility with deployments that configure a daily cap.
    daily_budget_usd: float = float(os.getenv("DAILY_BUDGET_USD", "10"))


settings = Settings()
