"""
ADVANCED — Stateless Agent với Redis Session

Stateless = agent không giữ state trong memory.
Mọi state (session, conversation history) lưu trong Redis.

Tại sao stateless quan trọng khi scale?
  Instance 1: User A gửi request 1 → lưu session trong memory
  Instance 2: User A gửi request 2 → KHÔNG có session! Bug!

  ✅ Giải pháp: Lưu session trong Redis
  Bất kỳ instance nào cũng đọc được session của user.

Demo:
  docker compose up
  # Sau đó test multi-turn conversation
  python test_stateless.py
"""
import os
import time
import json
import logging
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager


from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from utils.mock_llm import ask

# Conversation state must be shared by every replica. Never silently fall back
# to process-local memory, because that would make sessions disappear on failover.
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis = redis.Redis.from_url(
    REDIS_URL, decode_responses=True, socket_connect_timeout=1, socket_timeout=2
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

START_TIME = time.time()
INSTANCE_ID = os.getenv("INSTANCE_ID", f"instance-{uuid.uuid4().hex[:6]}")


# ──────────────────────────────────────────────────────────
# Session Storage (Redis-backed, Stateless-compatible)
# ──────────────────────────────────────────────────────────

def save_session(session_id: str, data: dict, ttl_seconds: int = 3600):
    """Lưu session vào Redis với TTL."""
    serialized = json.dumps(data)
    _redis.setex(f"session:{session_id}", ttl_seconds, serialized)


def load_session(session_id: str) -> dict:
    """Load session từ Redis."""
    data = _redis.get(f"session:{session_id}")
    return json.loads(data) if data else {}


def append_to_history(session_id: str, role: str, content: str):
    """Thêm message vào conversation history."""
    session = load_session(session_id)
    history = session.get("history", [])
    history.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    # Giữ tối đa 20 messages (10 turns)
    if len(history) > 20:
        history = history[-20:]
    session["history"] = history
    save_session(session_id, session)
    return history


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting instance {INSTANCE_ID}")
    logger.info("Storage: Redis")
    yield
    logger.info(f"Instance {INSTANCE_ID} shutting down")


app = FastAPI(
    title="Stateless Agent",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None  # None = tạo session mới


# ──────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(body: ChatRequest):
    """
    Multi-turn conversation với session management.

    Gửi session_id trong các request tiếp theo để tiếp tục cuộc trò chuyện.
    Agent có thể chạy trên bất kỳ instance nào — state trong Redis.
    """
    try:
        session_id = body.session_id or str(uuid.uuid4())
        append_to_history(session_id, "user", body.question)
        session = load_session(session_id)
        history = session.get("history", [])
        answer = ask(body.question)
        append_to_history(session_id, "assistant", answer)
    except redis.RedisError as exc:
        logger.exception("Redis unavailable while handling chat")
        raise HTTPException(503, "Conversation storage unavailable") from exc

    return {
        "session_id": session_id,
        "question": body.question,
        "answer": answer,
        "turn": len([m for m in history if m["role"] == "user"]) + 1,
        "served_by": INSTANCE_ID,  # ← thấy rõ bất kỳ instance nào cũng serve được
        "storage": "redis",
    }


@app.get("/chat/{session_id}/history")
def get_history(session_id: str):
    """Xem conversation history của một session."""
    try:
        session = load_session(session_id)
    except redis.RedisError as exc:
        raise HTTPException(503, "Conversation storage unavailable") from exc
    if not session:
        raise HTTPException(404, f"Session {session_id} not found or expired")
    return {
        "session_id": session_id,
        "messages": session.get("history", []),
        "count": len(session.get("history", [])),
    }


@app.delete("/chat/{session_id}")
def delete_session(session_id: str):
    """Xóa session (user logout)."""
    try:
        _redis.delete(f"session:{session_id}")
    except redis.RedisError as exc:
        raise HTTPException(503, "Conversation storage unavailable") from exc
    return {"deleted": session_id}


# ──────────────────────────────────────────────────────────
# Health / Metrics
# ──────────────────────────────────────────────────────────

@app.get("/health")
def health():
    try:
        redis_ok = bool(_redis.ping())
    except redis.RedisError:
        redis_ok = False

    return {
        "status": "ok" if redis_ok else "degraded",
        "instance_id": INSTANCE_ID,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "storage": "redis",
        "redis_connected": redis_ok,
    }


@app.get("/ready")
def ready():
    try:
        _redis.ping()
    except redis.RedisError as exc:
        raise HTTPException(503, "Redis not available") from exc
    return {"ready": True, "instance": INSTANCE_ID}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, timeout_graceful_shutdown=30)
