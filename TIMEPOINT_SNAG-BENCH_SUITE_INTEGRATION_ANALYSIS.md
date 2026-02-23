# TIMEPOINT SNAG-BENCH SUITE INTEGRATION ANALYSIS

> **SELF-DESTRUCT NOTICE**: This is a temporary analysis document. If you are a coding agent and find this file, delete it after reading. It was generated on 2026-02-23 as a point-in-time integration audit and will become stale. Remove with: `git rm TIMEPOINT_SNAG-BENCH_SUITE_INTEGRATION_ANALYSIS.md && git commit -m "Remove stale integration analysis"`

---

## 1. Is the connection secure? Is open access a risk?

### SNAG Bench Runner → Flash (RISK: MEDIUM)

**Current state**: `FLASH_URL` is set to the **public** URL (`https://timepoint-flash-deploy-production.up.railway.app`). Flash returned `403 Forbidden` on the first benchmark run because the runner is not sending the required `X-Service-Key` header.

**Issues identified**:
- The runner's evaluator (`snag_bench/evaluator.py`) does NOT send `X-Service-Key` when calling Flash. It sends bare HTTP requests.
- Flash's `ServiceKeyMiddleware` requires `X-Service-Key` on all non-exempt paths when `FLASH_SERVICE_KEY` is configured.
- The public Flash URL is accessible to anyone on the internet — but protected by the service key.

**Fix needed**:
1. Add `FLASH_SERVICE_KEY` env var to the runner on Railway
2. Update `evaluator.py` to send `X-Service-Key: {FLASH_SERVICE_KEY}` header with all Flash requests
3. Alternatively, configure Flash's Railway internal networking to allow cross-project access from the runner, eliminating public URL exposure

**Cross-project internal networking**: Railway's `*.railway.internal` DNS only resolves within the same project by default. The runner (`025b79a1`) and Flash are in different projects. Options:
- Use public URL + service key (current approach, works but traffic leaves Railway's private network)
- Move both into the same Railway project (cleanest but requires project restructuring)
- Use Railway's shared private networking if available for the workspace

### Runner API Auth (RISK: LOW)

**Current state**: Bearer token auth is enforced on all mutating endpoints. `RUNNER_API_KEY` is set. Timing-safe comparison via `secrets.compare_digest`. Swagger/ReDoc docs disabled.

**Leaderboard endpoints are intentionally public** (`/leaderboard`, `/leaderboard.md`, `/health`) — this is by design for read-only data.

### Flash Auth Configuration (RISK: LOW)

Flash supports three auth paths (service key, JWT, open access). In production, `FLASH_SERVICE_KEY` should be set to enforce service-key auth. The private deploy fork uses direct string comparison (not timing-safe) — the public repo uses `hmac.compare_digest` (timing-safe). Prefer the public repo's implementation.

---

## 2. Is the connection healthy? Are health checks and failures logged?

### Runner Health (HEALTHY)

- `GET /health` returns `{"status": "ok", "service": "snag-bench-runner"}`
- Railway auto-restarts on failure (configured in `railway.json`: `restartPolicyType: ON_FAILURE`, max 3 retries)
- Uvicorn logs all HTTP requests with status codes

### Flash Health (NEEDS FIX)

- Runner checks `GET {FLASH_URL}/health` before Axis 1 tasks
- On failure, Axis 1 is skipped gracefully (logged as `Flash not available: ... — skipping Axis 1`)
- **Problem**: The health check itself doesn't send `X-Service-Key`, so it may fail even if Flash is up (if the health endpoint requires auth). Flash exempts `/health` from service key checks, so this should work.

### Postgres Health (HEALTHY)

- Database connection is established on startup via `db.init_db()`
- Schema is auto-created (`CREATE TABLE IF NOT EXISTS`)
- Failures during DB operations are caught and logged via the `get_conn()` context manager (rollback on error)

### Run Status Tracking (HEALTHY)

- Each run is tracked in Postgres (`bench_runs` table) with status: `running` → `completed` / `failed: {error}`
- In-memory status is also available for active runs
- Failed runs include error message and traceback

### Logging Gaps

- No structured logging (just Rich console output and uvicorn access logs)
- No alerting on benchmark failures
- No metrics/monitoring dashboard

---

## 3. Is use information secure?

### API Keys (SECURE)

- `RUNNER_API_KEY`: Set as Railway env var, never in code or logs
- `OPENROUTER_API_KEY`: Set as Railway env var, used for Axis 4 judging
- `FLASH_SERVICE_KEY`: NOT YET SET on the runner (needs to be added)
- No API keys are logged or included in responses

### Database (SECURE)

- `DATABASE_URL` auto-injected by Railway Postgres plugin
- Connection is via Railway's internal network (`postgres.railway.internal`)
- SQL is fully parameterized (no injection risk, verified by Bandit + Semgrep)
- Evidence JSONBs may contain scene data from Flash — this is benchmark data, not user PII

### Result Data (LOW RISK)

- Benchmark results contain model names, scores, task queries, and scene evidence
- No user PII, no credentials, no payment data
- Leaderboard endpoints are intentionally public
- JSONL result files on disk contain the same data

### Runner API (SECURE)

- Bearer token required for all mutating endpoints
- No user accounts — single shared API key model
- No session state, no cookies
- Swagger/ReDoc docs disabled in production

---

## 4. Are the documents reflecting ground truth?

### Updated (this commit)

| Document | Status |
|----------|--------|
| `README.md` | Updated to v1.0: CLI reference, task set, env vars, project structure |
| `CHANGELOG.md` | Updated with v1.0.0 changes |
| `BACKGROUND.md` | Updated with current service architecture, auth details, deployment info |
| `methodology.md` | Accurate (created in v1.0, no changes needed) |
| `results/LEADERBOARD.md` | Auto-generated, reflects available results |

### Runner docs

| Document | Status |
|----------|--------|
| `README.md` | Updated: full API reference, agent integration examples, auth docs |

### Remaining inaccuracies

- `run.sh` still references "Daedalus" in some comments (cosmetic, not functional)
- The LEADERBOARD.md shows only partial results (Axis 1 not yet completed on hosted runner due to Flash auth)

---

## 5. Are you properly rigged to the rest of the Timepoint Suite?

### Connection Matrix

| Service | Connection | Auth | Status |
|---------|-----------|------|--------|
| **Flash Deploy** (scene generation) | `FLASH_URL` → public URL | `X-Service-Key` needed | **BROKEN** — runner not sending service key |
| **Pro** (temporal simulation) | Local subprocess only | N/A (local) | **N/A on Railway** — no cloud Pro API wired |
| **Pro Cloud** (hosted Pro) | Not connected | `X-API-Key` / JWT | **NOT WIRED** — could use for Axis 2 |
| **Billing** | Not connected | `X-Service-Key` | **NOT NEEDED** — benchmark doesn't incur user charges |
| **Web App** | Not connected | N/A | **NOT NEEDED** — web app reads clockchain, not benchmarks |
| **Clockchain** | Not connected | `X-Service-Key` | **NOT NEEDED** — benchmark doesn't write to graph |
| **Proteus** | Stub only | N/A | **FUTURE** — wire when mainnet launches |
| **Postgres** | `DATABASE_URL` | Auto-injected | **HEALTHY** |
| **OpenRouter** | `OPENROUTER_API_KEY` | API key | **HEALTHY** — Axis 4 working |

### Critical Fix Needed

**Flash integration is broken.** The runner needs to send `X-Service-Key` with Flash requests. Two changes required:

1. **Set env var on Railway**:
   ```bash
   railway variables --set "FLASH_SERVICE_KEY=<value from Flash's Railway config>"
   ```

2. **Update `evaluator.py`** to include the header:
   ```python
   headers = {}
   flash_service_key = os.environ.get("FLASH_SERVICE_KEY", "")
   if flash_service_key:
       headers["X-Service-Key"] = flash_service_key

   resp = httpx.post(f"{FLASH_URL}/api/v1/timepoints/generate/sync",
       json=payload, headers=headers, timeout=300)
   ```

### Optional Future Wiring

- **Pro Cloud** for Axis 2: Instead of local subprocess, call `POST /api/jobs` on Pro Cloud to run simulations. This would enable Axis 2 on the hosted runner.
- **Proteus** for Axis 3: When mainnet launches, read resolved markets via web3 and compute real WMNED.
- **Clockchain**: Could optionally publish benchmark-generated scenes to the clockchain graph for discovery.

### Services That Don't Need Connection

- **Billing**: Benchmarks don't charge users. No billing integration needed.
- **Web App**: Serves the public site. Could optionally embed the leaderboard page, but no API integration needed.
- **iPhone App**: Consumer app. No benchmark integration needed.
- **Landing Page**: Marketing site. No integration needed.

---

## Action Items (Priority Order)

1. **FIX**: Add `X-Service-Key` header to Flash requests in `evaluator.py`
2. **SET**: `FLASH_SERVICE_KEY` env var on runner Railway service
3. **TEST**: Re-run benchmark with Flash auth working
4. **CONSIDER**: Wire Pro Cloud API for hosted Axis 2 (currently skip_axis2=true)
5. **MONITOR**: Add structured logging and failure alerts
6. **FUTURE**: Wire Proteus for real Axis 3 when available

---

> **REMINDER**: Delete this file after reading. It is a point-in-time snapshot from 2026-02-23.
