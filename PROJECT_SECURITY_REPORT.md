# Project & Security Report — Üretim Performans Takip Uygulaması

**Date:** 2026-06-10 · **Scope:** full repository (backend, frontend, data pipeline) · **Method:** static code review + configuration audit

---

## Part 1 — What the Project Is and How It Works

### 1.1 Purpose

A production performance tracking application (Magna case study). It ingests raw MES production data from CSV, detects and manages data-quality problems, lets an operator review/correct/reject records, and submits validated, aggregated day×shift results to an external production API.

### 1.2 Architecture

```
backend/   FastAPI + SQLAlchemy 2.0 (async) + aiosqlite (WAL mode)
  api/         thin routers: import, records, validation, reports, sync, settings, alerts, mock_api
  services/    all business logic: import, record, report, validation, sync, scheduler
  validation/  engine.py (orchestration) + rules.py (one function per rule)
  seed.py      default validation-rule catalog (seeded idempotently at startup)
frontend/  React 18 + Vite + Ant Design 5 + Recharts
  pages/       Dashboard, ImportData, Records, ValidationReport, LossAnalysis, SyncManager, Settings
data/      production_data.csv (case data) + production_data_50k.csv (60K scale test)
```

**Database (7 tables):**

| Table | Role |
|---|---|
| `production_records` | One row per CSV line. `original_data` stores the untouched CSV row as JSON (**data lineage** — corrections never destroy the source of truth). Status: `pending → clean / warning / error / corrected / rejected / submitted` + `is_hidden`. |
| `validation_errors` | Findings per record (severity, field, expected vs actual, suggested action). |
| `validation_rules` | Rule catalog with thresholds/severity/active flag — **configuration lives in the DB**, edited from the Settings UI, read by the engine at runtime. |
| `audit_logs` | Every edit/status change: field, old value, new value, reason. |
| `import_batches` | SHA-256 file hash (duplicate upload detection) + progress fields for the async import. |
| `sync_logs` | `UNIQUE(production_date, shift)` — **idempotent submission**: a day/shift is sent once unless explicitly forced. |
| `app_settings` | Auto-sync configuration (enabled + interval). |

### 1.3 The Key Metrics: A, P, Q, OEE

These are the standard OEE (Overall Equipment Effectiveness) components, on a 0–100 scale:

- **A — Availability (Kullanılırlık):** `A = Çalışma Süresi / (Çalışma Süresi + Plansız Duruş) × 100` — how much of the planned time the machine actually ran. Planned stops do not penalize A; unplanned stops do.
- **P — Performance (Performans):** actual output speed vs ideal cycle time. In this dataset P > 100 occurs (a known MES artifact — usually a wrong ideal cycle time), which the app detects rather than silently fixes.
- **Q — Quality (Kalite):** `Q = (Üretilen − Hatalı) / Üretilen × 100` — share of produced units that were good.
- **OEE:** `OEE = A × P × Q / 10000` — the product of the three (divided by 10000 because each component is a percentage).

Reports use **duration-weighted averages** (weighted by Çalışma Süresi), not naive means, so a 10-minute run doesn't count as much as an 8-hour run. In the Loss Analysis (OEE waterfall) A/P/Q are clamped to 100 so the P>100 artifact can't produce negative losses.

### 1.4 Data-Quality Handling (End-to-End Flow)

1. **Upload** (`POST /api/import/upload`): the file is hashed (SHA-256) — re-uploading the same file returns 409 with the existing batch. Quick row/column sanity check (18 expected columns), then the batch row is created and the request **returns immediately**.
2. **Background import:** pandas parses the CSV (with encoding detection — the case file is not plain UTF-8), rows are bulk-inserted in chunks while the batch row tracks progress; the UI polls `GET /api/import/batches/{id}`. 60K rows ≈ 10s thanks to bulk inserts + SQLite WAL.
3. **Validation engine** runs over the batch and writes findings + per-record status (worst finding wins: error > warning > clean). User-owned statuses (corrected/rejected/submitted) are never clobbered by re-validation.
4. **Review:** the Records page shows errors per record; the operator can **edit** (every field change is audit-logged with old/new value and a reason, then the record is re-validated and marked `corrected`), **reject**, **hide**, or restore.
5. **Sync:** only *countable* records (`clean`, `warning`, `corrected`, not hidden) are aggregated per day×shift. Rejected/error/hidden data **never reaches the target system**. Submission goes through `ProductionApiClient` with retry policy (429 → honor `Retry-After`, 5xx/network → exponential backoff 2/4/8s, max 3 attempts; 401/422/413 never retried). Successful day/shifts are recorded in `sync_logs` and not re-sent unless forced. An opt-in APScheduler job (default **off**) can auto-submit ready day/shifts periodically.

### 1.5 The Validation Rule System

Rule-registry pattern: every rule is a self-contained function with the contract `check(record, cfg) -> list[Finding]`, registered by `rule_code`. Thresholds, severity, and on/off come from the DB row (`cfg`), so **nothing is hardcoded** — tuning a rule is a Settings-UI action, and adding a rule = one function + one seed row (Open/Closed principle).

Rule categories:

| Category | Examples |
|---|---|
| **Missing values** | shift, work time, station, stop time, product, job order, work center empty |
| **Sentinel** | the MES placeholder `-10` across all 10 numeric fields (owned by one rule so others skip it — no double-flagging) |
| **Negative values** | work time, produced qty, defect qty < 0 |
| **Out of range** | A ∉ [0,100]; Q with warning/error tiers; OEE/P/work-time two-tier (`> warning_threshold` → warning, `> error_threshold` → error) |
| **Formula consistency** | `OEE ≠ A×P×Q/10000`, `Q ≠ (Üretilen−Hatalı)/Üretilen×100`, `A ≠ Çalışma/(Çalışma+Plansız)×100` (each with a configurable tolerance) |
| **Domain logic** | defects > production |
| **Systematic** | a product×station combination where *all* rows have P > threshold — flags a wrong ideal cycle time rather than per-row noise |
| **Statistical (IQR)** | `STATISTICAL_OEE_OUTLIER` and `PRODUCTION_RATE_OUTLIER`: within each product×station group, values outside `median ± k·IQR` (default k=3, min group size 8) — catches contextual anomalies fixed thresholds miss. Detection-only, never auto-corrects. |

Severity drives the suggested action: error → reject, warning → correct, info → inspect.

---

## Part 2 — Security Assessment

**Overall posture:** appropriate for a local/dev case-study deployment. No injection-class vulnerabilities found. The dominant risks are **absence of authentication** and **unbounded upload size** — both must be addressed before any shared/production deployment.

### 2.1 Findings

#### ACCEPTED RISK — No authentication or authorization on application endpoints
Every `/api/*` route is unauthenticated. The only auth in the codebase protects the *mock target* API (`X-Production-Key` check in `backend/api/mock_api.py`), not the app itself.
**Decision (2026-06-10):** accepted — the project runs locally only and will not be deployed to any platform. Revisit if that ever changes.

#### FIXED — Unbounded file upload (memory-exhaustion DoS)
`backend/api/import_routes.py` previously did `raw = await file.read()` with no size cap, loading the entire upload into RAM. A multi-GB upload could OOM the process.
**Fix (2026-06-10):** uploads are now stream-read in 1 MB chunks via `_read_capped()` and rejected with **413** the moment they exceed the cap — an oversized file is never fully buffered. The limit is configurable via `max_upload_mb` in `backend/config.py` (default 50 MB; the 60K-row scale-test file is ~6 MB). Verified: 51 MB upload → 413; normal upload unaffected; all 37 backend tests pass.

#### MEDIUM — No rate limiting / abuse controls
No throttling on upload, re-validate-all, or submit endpoints; repeated background imports can also be stacked without bound.
**Recommendation:** add rate limiting (e.g. slowapi) and cap concurrent background import jobs.

#### MEDIUM — Plain-HTTP target API and default credentials fallback
`backend/config.py` defaults: `api_base_url = "http://localhost:8000/mock"`, `api_key = "test-api-key-2025"`. If deployed without env configuration, the app silently runs with test credentials; if pointed at an `http://` production URL, the API key transits in cleartext.
**Recommendation:** in production, fail fast when `API_KEY` is unset and enforce `https://` for non-localhost base URLs.

#### LOW — CORS configured with credentials
CORS allows `http://localhost:5173` with `allow_credentials=True` and `allow_methods/headers=["*"]`. Fine for dev; must be revisited per deployment origin.

#### LOW — Internal error text surfaced to clients
Failed imports store `str(exc)[:500]` into `import_batches.error_message`, which the UI displays — may leak file paths/stack fragments. Map known failures to friendly messages and log the rest server-side.

#### LOW — Potential CSV/Excel formula injection in exports (verify)
The frontend exports CSV client-side (Blob) and PDF (jsPDF). If exported cells can begin with `=`, `+`, `-`, `@`, Excel will execute them as formulas. Not confirmed exploitable — sanitize by prefixing such cells with `'` in the export helper.

### 2.2 What Was Checked and Found Clean

- **SQL injection — clean.** All queries use SQLAlchemy ORM constructs (`select/insert/update`); the only raw `execute` calls are constant `PRAGMA` statements in `backend/database.py`. No string-built SQL anywhere.
- **XSS — clean.** React escapes output by default; no `dangerouslySetInnerHTML`, `innerHTML`, or `eval` anywhere in `frontend/src`. CSV-sourced strings are rendered through AntD components.
- **Secrets hygiene — clean.** `.env` is gitignored (only `.env.example` is tracked); no real credentials in the repo; secrets are read via pydantic-settings.
- **Code-exec primitives — clean.** No `eval`/`exec`/`pickle`/`os.system`/`shell=True`/`yaml.load` in application code.
- **Server-side input validation — good.** Pydantic schemas on every endpoint; status actions allow-listed; editable record fields allow-listed (`_EDITABLE_FIELDS`) so mass-assignment of protected columns (status, lineage JSON) is not possible; shift constrained to 1–3; mock API validates auth → size → JSON → schema in the right order.
- **Dependencies — current.** fastapi 0.115.6, sqlalchemy 2.0.36, pandas 2.2.3, httpx 0.28.1, pydantic 2.10.4, python-multipart 0.0.20 (includes the 2024 multipart DoS fixes); frontend React 18 / antd 5 / axios 1.7.9. No known critical CVEs at these pins; run `pip-audit` and `npm audit` periodically.
- **Data integrity safeguards — good.** Original row preserved as JSON; every change audit-logged with reason; idempotent sync (`UNIQUE(date, shift)`); SHA-256 duplicate-file detection; rejected/error/hidden data excluded from submission; auto-sync off by default.

### 2.3 Priority Fix List

1. ~~Add authentication to all `/api` routes~~ — accepted risk, local-only project.
2. ~~Cap upload size on `/api/import/upload`~~ — **fixed** (50 MB streaming cap, 413 on excess).
3. Fail fast on missing `API_KEY` / enforce HTTPS for non-local targets (MEDIUM — moot while local-only).
4. Add rate limiting and background-job concurrency caps (MEDIUM — moot while local-only).
5. Sanitize CSV export cells; genericize import error messages (LOW).
