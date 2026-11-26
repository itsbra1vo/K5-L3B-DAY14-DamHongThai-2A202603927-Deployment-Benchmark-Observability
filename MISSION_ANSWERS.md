# Day 14 Lab — Mission Answers

> Student: Dam Hong Thai (repository name: `K5-L3B-DAY14-DamHongThai-2A202603927-Deployment-Benchmark-Observability`)  
> Status: answers and evidence recorded from this workspace on 2026-11-26. Items that require a public cloud deployment or a Linux signal probe are explicitly marked pending.

## Part 1: Localhost vs Production

### Exercise 1.1: Production anti-patterns addressed

1. Runtime settings and credentials are read from environment variables; secrets are not embedded in the deployment configuration.
2. The agent has `/health` and `/ready` endpoints. Readiness includes dependency state, so a live process with unavailable Redis is not advertised as ready.
3. API requests are protected by API key authentication; the full service also enforces rate limits and a Redis-backed monthly cost guard.
4. Shared conversation and protection state is kept in Redis rather than process memory, allowing instances to restart or scale independently.
5. Structured JSON logs, Prometheus metrics, and OpenTelemetry traces provide operational evidence.

### Exercise 1.2: Why these issues matter

A committed key can be copied and abused; revoke it and rotate all dependent credentials immediately, then inspect usage. A stateful process loses sessions on restart and cannot reliably serve requests through another replica. Dev/prod parity means using the same deployment shape and configuration model locally and in production, so differences surface before release.

### Exercise 1.3: Develop and production comparison

| Feature | Develop | Production | Why it matters |
|---|---|---|---|
| Configuration | Local defaults and mock settings | Environment-driven settings and secrets | Same image can run in multiple environments without baking credentials in |
| State | Process-local/in-memory | Redis-backed shared state | Requests can reach different replicas and survive restarts |
| Traffic | Direct local app | Docker Compose services behind Nginx | Central routing and repeatable local deployment |
| Protection | Lab/mock behavior | API key, rate limit, monthly cost guard | Limits unauthorized use and spend |
| Operations | Local console | Health/readiness, JSON logs, Prometheus, traces | Supports deployment checks and diagnosis |

## Part 2: Docker

### Exercise 2.1: Dockerfile answers

1. The basic image uses `python:3.11`; the production image uses a multi-stage `python:3.11-slim` builder/runtime pattern.
2. `WORKDIR /app` sets the working directory for subsequent instructions and the container process.
3. Dependency manifests are copied and installed before application source to preserve the dependency build layer when only source changes.
4. The basic Dockerfile uses exec-form `CMD`; it does not define an `ENTRYPOINT`.
5. The production image copies only runtime dependencies and application files into its runtime stage and runs as a non-root user.

### Exercise 2.2: Build and run

The final production image was built by the full checker and the container runtime checks were exercised. The root `DOCKER_LAB_REPORT.md` records that the separate basic-vs-production image comparison and basic image run were not measured; the 160 MB result belongs to `06-lab-complete`, not a claimed apples-to-apples comparison. `COPY requirements.txt` followed by dependency installation keeps that layer reusable. `.dockerignore` should exclude `.env`, virtual environments, caches, Git metadata, and local data to avoid leaking secrets or bloating the build context. Mount a read-only or persistent volume for runtime files that must be read or retained.

### Exercise 2.3: Image-size comparison

The checker built the final `06-lab-complete` image at **160 MB**, below the 500 MB target. A comparable basic image build was not recorded, so a develop-vs-production size difference cannot be stated without fabricating a measurement. See `DOCKER_LAB_REPORT.md` for the earlier image comparison status.

## Part 3: Cloud Deployment

A Render Blueprint is present in the root `render.yaml`; the `06-lab-complete` directory also has deployment configuration. No service has been deployed, so there is no public URL, public endpoint test, or genuine cloud dashboard/running/test screenshot. The exact status and test commands are in `DEPLOYMENT.md`. Local Docker verification does not count as a cloud deployment.

Serverless can be a poor fit when an agent needs long-lived connections, warm model state, or predictable latency; cold start is the delay while a platform initializes a stopped instance and loads its app/model, which increases first-request latency. Move from a lab platform to Cloud Run when production needs stronger traffic controls, regional deployment, IAM integration, autoscaling configuration, and managed CI/CD, after measuring the operational and cost tradeoffs.

## Part 4: API Security

### Exercises 4.1–4.3: Test results

The complete production checker exercised the local Docker service and reported:

- Missing API key: **401**; valid key: **200**.
- Rate limit: **429** after the configured allowance.
- Cost guard: **402** when the budget is exhausted.
- Redis-backed state remains available after an application restart.
- Health/readiness behavior was checked, including readiness failure when Redis is unavailable.

For the discussion: API keys suit service-to-service credentials; JWTs suit signed, short-lived user claims; OAuth2 is appropriate when delegated authorization and third-party identity flows are needed. Set rate limits from measured capacity and cost, then use separate quotas by user/plan. On suspected key leakage, revoke/rotate it, review logs and spend, and notify affected owners.

### Exercise 4.4: Cost guard

The production implementation reserves estimated request cost in Redis before the model call and reconciles against observed token usage afterward. A monthly per-user cap is configured through environment settings; requests fail closed if the state store is unavailable. API keys, Redis URLs, and other secrets belong in the platform environment, not committed files.

## Part 5: Scaling & Reliability

The completed service uses Redis for shared state, health and readiness endpoints, request tracking for graceful shutdown, and Docker Compose for repeatable multi-service operation. The full checker verified stateless behavior across restart, Redis-loss readiness behavior, rate limiting, and cost protection. Its Docker stop test passed. Its separate runtime SIGTERM probe could not run on Windows; see the checker summary below. A public multi-replica cloud deployment has not been performed. Liveness tells the platform to restart an unhealthy process; readiness tells the load balancer whether it should receive traffic. Graceful shutdown stops readiness first and waits for in-flight requests. Redis lets any replica read the same session and quota state, while Nginx distributes requests. For reliability, monitor latency/error rate and dependencies, keep state external, and test dependency loss and replica restarts.

## Part 6: Production-ready checker

Command: `python check_production_ready.py` from `06-lab-complete/`, run with Docker available on 2026-11-26.

**Result: 11/12 criteria; 40/40 checks passed.** Final image size: **160 MB**. The checker printed `CHƯA ĐẠT` because its runtime SIGTERM probe was not supported in this Windows environment. The Docker stop test itself passed (exit code 0). The provided checker is unmodified. A Linux run is still required for the requested `PASS 12/12` result.

### Checklist Deliverable summary

| # | Criterion | Result |
|---:|---|---|
| 1 | Dockerfile (multi-stage, < 500 MB) | PASS — 160 MB |
| 2 | docker-compose.yml (agent + redis) | PASS |
| 3 | .dockerignore | PASS |
| 4 | Health endpoint (GET /health) | PASS |
| 5 | Readiness endpoint (GET /ready) | PASS |
| 6 | API key authentication | PASS |
| 7 | Rate limiting | PASS |
| 8 | Cost guard | PASS |
| 9 | Configuration from environment variables | PASS |
| 10 | Structured logging | PASS |
| 11 | Graceful shutdown | PARTIAL — Docker stop passed; direct Windows SIGTERM probe unavailable |
| 12 | Public URL ready (Railway / Render config) | PASS — deployment configuration present; this does not establish a live URL |
The checker reported **40/40 individual checks passed** while marking the graceful-shutdown criterion incomplete due to the unsupported probe. This is why the overall result remains 11/12, not 12/12.

## AI usage log

- Used Codex to inspect the submission requirements, implement/fix lab code and observability artifacts, run the production checker, consolidate reports/evidence into the required root structure, and draft this evidence-based summary.
- Human review is required for the deployment decision and any cloud credentials; no cloud service or secret was created as part of this submission.

## Remaining submission items

- Deploy to a public platform, record a working URL and four actual endpoint outcomes, and capture the three genuine deployment screenshots.
- Run the provided checker on a Linux host to obtain the required `PASS 12/12`.
- The available Locust CSVs are baseline and slow-fault runs; scale-1/scale-3 CSVs were not produced. Do not label them as scale comparison results.


- One local `01-localhost-vs-production/production/.env` file exists in the working tree but is ignored and untracked by Git. Do not force-add it; remove it before making an archive or sharing the working directory. The tracked example is `.env.example`.
