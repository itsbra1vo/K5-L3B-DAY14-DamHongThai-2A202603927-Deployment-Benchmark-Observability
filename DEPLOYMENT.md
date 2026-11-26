# Deployment record

## Status

Deployment has not yet been created. No cloud deployment has been created in this workspace, so there is no public URL or live cloud check result to report. Docker-based local checks were later run successfully; see `MISSION_ANSWERS.md`. The repository-root `render.yaml` is configured as a Render Blueprint for both the web service and Redis. Local HTTP checks were run on 2026-11-26; see below. Do not treat these as a cloud deployment.

## Target

- Platform: Render Blueprint (configured by repository-root `render.yaml`); Railway alternative: `06-lab-complete/railway.toml`
- Public URL: not created yet
- Region/service name: `<fill after deploy>`
- Deploy date: `<YYYY-MM-DD>`

## Environment variables

Configure these in the hosting platform's service settings. Set secret values in the platform dashboard/CLI and never commit them here.

| Variable | Value to configure |
| --- | --- |
| `AGENT_API_KEY` | Generate a long random secret; do not record the value here |
| `REDIS_URL` | Private connection URL of the managed Redis service |
| `RATE_LIMIT_PER_MINUTE` | `10` (or the chosen limit) |
| `DAILY_BUDGET_USD` | `10` (or the chosen cap) |
| `MONTHLY_BUDGET_USD` | `10` (or the chosen cap) |
| `ENVIRONMENT` | `production` |
| `PORT` | Supplied by the platform; the container listens on it |

## Render Blueprint

The repository-root `render.yaml` creates a Docker web service and a Redis Key Value service in Singapore, wires `REDIS_URL` from the Redis service, generates `AGENT_API_KEY`, and checks `/health`. The Blueprint uses free plans for a no-cost lab trial; Render's free Key Value plan does not persist data, so use a paid persistent plan if rate-limit and cost state must survive Redis restarts.

Connect this GitHub repository to Render as a Blueprint and deploy. Render generates the API key; retrieve it from the service environment settings for the authenticated request without committing it. When deployment succeeds, fill in the service URL, region, and deploy date above, then record actual endpoint responses below.

## Railway alternative

The existing `railway.toml` selects the Dockerfile and `/health` deployment check. Set the Railway service root directory to `06-lab-complete`, create a Redis service in the same project, and connect `REDIS_URL` to its private URL. Set `AGENT_API_KEY` as a secret in the dashboard; do not commit its literal value.

```powershell
railway login
railway init
railway add --database redis
railway variables set RATE_LIMIT_PER_MINUTE=10 DAILY_BUDGET_USD=10 MONTHLY_BUDGET_USD=10 ENVIRONMENT=production
railway up
railway domain
```

Set `AGENT_API_KEY` and `REDIS_URL` in the Railway Variables page (or use the CLI's interactive secret input). Wait until the deployment is healthy before recording the generated domain.

## Public checks

Run from this directory in PowerShell after setting the URL and API key in the current session. These commands print response codes and the successful `/ask` JSON; keep the key out of screenshots and logs.

```powershell
$base = 'https://<your-generated-domain>'
$key = Read-Host 'AGENT_API_KEY'
Invoke-WebRequest "$base/health" -Method Get
Invoke-WebRequest "$base/ready" -Method Get
try { Invoke-WebRequest "$base/ask" -Method Post -ContentType 'application/json' -Body '{"question":"deployment check"}' } catch { $_.Exception.Response.StatusCode.value__ }
Invoke-RestMethod "$base/ask" -Method Post -Headers @{ 'X-API-Key' = $key } -ContentType 'application/json' -Body '{"question":"deployment check"}'
```

Expected: `/health` and `/ready` return 200; unauthenticated `/ask` returns 401; authenticated `/ask` returns 200. Record the actual outcomes and date here after running the checks.

## Local verification (2026-11-26)

Started the app with a temporary local API key and no Redis service. Results: `GET /health` â†’ 200; `GET /ready` â†’ 503; unauthenticated `POST /ask` â†’ 401; authenticated `POST /ask` â†’ 503 because Redis was unavailable. No public URL or authenticated successful response has been verified yet.

## Configuration comparison: `render.yaml` vs `railway.toml`

| Aspect | Render `render.yaml` | Railway `railway.toml` |
| --- | --- | --- |
| Format and scope | YAML Blueprint describing multiple services/resources | TOML configuration for one Railway service deployment |
| Provisioning | Declares web service and Redis Key Value resource together | Configures Docker build and deploy behavior; Redis must be provisioned/connected separately |
| Docker build | `rootDir`, `dockerfilePath`, and `dockerContext` handle this repo's monorepo layout | Uses Dockerfile builder; set Railway service root directory to `06-lab-complete` |
| Health check | `healthCheckPath: /health` | `healthcheckPath = "/health"` plus timeout and restart policy |
| Secret/config | Generates `AGENT_API_KEY`; references Redis `connectionString`; sets limits and environment | Variables and secret values are configured in Railway service variables |
| Best fit here | Reproducible one-shot setup including Redis | Simple single-service deploy when Railway project and Redis already exist |

Render Blueprint fields follow the [official Blueprint reference](https://render.com/docs/blueprint-spec); Railway's TOML settings are documented in [Config as Code](https://docs.railway.com/config-as-code/reference). Railway Config as Code is deprecated in favor of Infrastructure as Code; existing files are supported for legacy services through 2026-12-01 according to current Railway documentation.

## Optional GCP Cloud Run CI/CD reading

`03-cloud-deployment/production-cloud-run/cloudbuild.yaml` describes a Cloud Build pipeline: install dependencies/run pytest, build and tag a Docker image, push it to Container Registry, and deploy to Cloud Run in `asia-southeast1`. `service.yaml` separately describes runtime scaling, resource limits, Secret Manager references, and probes. These are examples, not an active pipeline; this repository has no configured GCP project/trigger, and the pipeline's image/build paths and environment variables should be aligned with `06-lab-complete` before using it.

## Evidence

Save genuine screenshots of the platform deployment/variables page (with secret values obscured) and the public endpoint checks in [`screenshots/`](screenshots/). No screenshots are included until a live deployment has been created and verified.


## Root submission screenshots

No live deployment screenshots are included: the service has not been deployed to a public platform. The Part 7 evidence screenshots are in the repository-root screenshots/ directory.

