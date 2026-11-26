# Section 4 — API Gateway & Security

## Mục tiêu học
- Hiểu tại sao cần lớp bảo vệ trước agent
- Implement API Key authentication
- Implement JWT authentication (nâng cao)
- Rate limiting và cost protection

---

## Ví dụ Basic — API Key Authentication

```
develop/
├── app.py              # Agent với API Key auth
└── requirements.txt
```

### Chạy thử
```bash
cd develop
pip install -r requirements.txt
AGENT_API_KEY=my-secret-key python app.py

# Test với key hợp lệ
curl -H "X-API-Key: my-secret-key" http://localhost:8000/ask \
     -X POST -H "Content-Type: application/json" \
     -d '{"question": "hello"}'

# Test không có key → 401
curl http://localhost:8000/ask -X POST \
     -H "Content-Type: application/json" \
     -d '{"question": "hello"}'
```

---

## Ví dụ Advanced — JWT + Rate Limiting + Cost Guard

```
production/
├── app.py              # Full security stack
├── auth.py             # JWT token logic
├── rate_limiter.py     # In-memory rate limiter
├── cost_guard.py       # Token budget và spending alerts
├── test_advanced.py    # Test suite
└── requirements.txt
```

### Chạy thử
```bash
cd production
pip install -r requirements.txt
python app.py

# Lấy JWT token
curl -X POST http://localhost:8000/auth/token \
     -H "Content-Type: application/json" \
     -d '{"username": "student", "password": "demo123"}'

# Dùng token
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/ask \
     -X POST -H "Content-Type: application/json" \
     -d '{"question": "what is docker?"}'

# Test rate limit: spam 20 requests liên tiếp
# Lấy token rồi gửi 20 requests — request 11+ sẽ bị chặn (429)
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
     -H "Content-Type: application/json" \
     -d '{"username": "student", "password": "demo123"}' \
     | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

for i in $(seq 1 20); do
  printf "Request %2d: " $i
  curl -s -H "Authorization: Bearer $TOKEN" \
       -X POST http://localhost:8000/ask \
       -H "Content-Type: application/json" \
       -d '{"question": "what is docker?"}' \
       | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('answer','')[:60] if 'answer' in d else f'❌ {d.get(\"detail\",d)}')"
done
```

---

## Luồng bảo vệ

```
Request
  → Auth Check (401 nếu fail)
  → Rate Limit (429 nếu vượt quota)
  → Input Validation (422 nếu invalid)
  → Cost Check (402 nếu hết budget)
  → Agent (200 nếu mọi thứ OK)
```

---

## Câu hỏi thảo luận

1. Khi nào nên dùng API Key vs JWT vs OAuth2?
2. Rate limit nên đặt bao nhiêu request/phút cho một AI agent?
3. Nếu API key bị lộ, bạn phát hiện và xử lý như thế nào?
# API Security lab

## API key authentication (develop)

`develop/app.py` protects `POST /ask` with the `verify_api_key` FastAPI dependency. A missing key returns **401** and a wrong key returns **403**. The key is read from `AGENT_API_KEY` at process start; rotate it by changing the secret in the deployment environment and restarting/redeploying the service. Do not commit real keys. The bundled fallback is only for local learning.

```powershell
$env:AGENT_API_KEY = 'local-lab-key'
cd develop
pip install -r requirements.txt
python app.py
```

Send the key using `X-API-Key: local-lab-key`. Try with no header and with `X-API-Key: wrong` to observe 401 and 403.

## JWT and rate limits (production)

`POST /auth/token` checks the demo user credentials in `production/auth.py` and signs a 60-minute HS256 token with `JWT_SECRET`. `verify_token` validates signature and expiry for protected endpoints. Credentials are `student / demo123` (user) and `teacher / teach456` (admin); use a non-default `JWT_SECRET` outside the lab.

The rate limiter is an in-process **sliding timestamp window**: users get **10 requests per 60 seconds**, admins **100 per 60 seconds**. The role decides which limiter instance `/ask` uses. A rejected request returns **429**, `Retry-After`, and `X-RateLimit-*` headers. This demo limiter is per-process, so production multi-instance deployments should move it to shared Redis.

## Redis monthly cost guard

The production guard reserves estimated cost atomically in Redis before calling the LLM, then reconciles it to measured usage. Each user is limited to **$10 per UTC calendar month**. The Redis key includes `YYYY-MM`; a new month starts with a fresh budget. If Redis is unavailable, protected calls return 503 (fail closed).

Start Redis in one terminal:

```powershell
docker run --rm --name api-security-redis -p 6379:6379 redis:7-alpine
```

In another terminal, from `04-api-gateway/production`:

```powershell
pip install -r requirements.txt
$env:JWT_SECRET = 'local-lab-jwt-secret-change-me'
$env:REDIS_URL = 'redis://localhost:6379/0'
python app.py
```

Get a JWT, then call `/ask` with `Authorization: Bearer <token>`. Use `/me/usage` to inspect monthly usage. Send 11 rapid `/ask` calls as `student` to see the 11th rejected with 429; `teacher` can make 100 in the same window. Reset the local demo counters with `docker exec api-security-redis redis-cli FLUSHDB`.

The demo credentials, API key fallback, in-memory rate limiter, and example secrets are for learning only. Use a user store, secret manager, and shared Redis rate limiter in a real deployment.
