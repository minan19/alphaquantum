# Alpha Quantum

Alpha Quantum is an enterprise management platform combining ERP, finance, operations, and AI-driven decision support.

## What Is Set Up

- Layered FastAPI architecture (`app/` package)
- SQLite-backed repository with thread-safe updates
- DB-backed identity (users, roles, refresh tokens, revoke list)
- SQL migration layer (`schema_migrations`) with apply/rollback
- Analysis service for risk scoring and action generation
- Dynamic HTML dashboard at `/dashboard`
- JWT auth + role-based access for mutation endpoints
- Refresh token rotation + revoke/logout
- Password rotate + admin user/role CRUD endpoints
- Role-based permission matrix (`permissions`, `role_permissions`)
- Audit log persistence (`who`, `when`, `which endpoint`, status, duration)
- Login rate limit (memory + optional Redis distributed backend) and production security guardrails
- Modular engine layer (`company_engine`, `inventory_engine`, `finance_engine`)
- Finance ledger + cashflow + forecast endpoints
- Market data engine (OHLCV cache + technical analysis: trend/RSI/MACD)
- Market intelligence engine (TR/EU/Global borsa kaynak katalogu + site adaptors + recommendation feed)
- Backtest engine (signal strategy quality: win-rate, edge, drawdown)
- Global intelligence engine (central banks + World Bank + global market report)
- Public institution web intelligence engine (URL scan + term matching + summary + table extraction)
- Tender dossier engine (institution spec parsing + compliance matrix + draft dossier output)
- Procurement engine (RFQ/quote comparison + weighted decision + auto purchase order + tender-linked plan)
- Feasibility engine (sector-agnostic multi-scenario investment analysis + recommendation + persistence)
- International operations engine (country-based management/consulting/installation/import-export project development)
- Strategic ecosystem orchestration engine (feasibility + international + procurement activation in one flow)
- Integration connector engine (canonical mapping preview + readiness score + prioritized sync queue/dispatch + retry/DLQ worker)
- Connector worker leader-lock lease (single active worker safety in multi-instance deployment)
- Legacy endpoints preserved for backward compatibility
- Versioned API endpoints under `/api/v1/*`
- Request logging middleware with `X-Request-ID`

## Enterprise Layer Model

- 7-layer kurumsal mimari modeli dokümante edildi:
  - Kullanıcı/İstemci
  - Platform/API
  - Backend/Veri
  - Fiziksel/Donanım
  - Ürün & Çözüm
  - Dijital Platform
  - Hizmet
- Ayrıntılı doküman:
  - [ARCHITECTURE_LAYER_MODEL.md](/Users/mustafainan/alpha-quantum/ARCHITECTURE_LAYER_MODEL.md)
- Blueprint içi resmi referans:
  - [MASTER_BLUEPRINT.md](/Users/mustafainan/alpha-quantum/MASTER_BLUEPRINT.md)
- Phase/Owner/KPI/SLA yürütme planı:
  - [LAYER_EXECUTION_PLAN.md](/Users/mustafainan/alpha-quantum/LAYER_EXECUTION_PLAN.md)
- Sprint backlog (Epic > Story > Task):
  - [SPRINT_BACKLOG.md](/Users/mustafainan/alpha-quantum/SPRINT_BACKLOG.md)
- Haftalık icra planı (ilk 5 görev):
  - [WEEKLY_ACTIONS_2026-03-21.md](/Users/mustafainan/alpha-quantum/WEEKLY_ACTIONS_2026-03-21.md)
- Owner atama kaydı:
  - [TEAM_OWNERS.md](/Users/mustafainan/alpha-quantum/TEAM_OWNERS.md)
- Governance karar notu:
  - [GOVERNANCE_REVIEW_NOTE_2026-03-21.md](/Users/mustafainan/alpha-quantum/GOVERNANCE_REVIEW_NOTE_2026-03-21.md)
- KPI/SLA sözlüğü:
  - [KPI_SLA_DICTIONARY.md](/Users/mustafainan/alpha-quantum/KPI_SLA_DICTIONARY.md)
- Backup/restore runbook:
  - [BACKUP_RESTORE_RUNBOOK.md](/Users/mustafainan/alpha-quantum/BACKUP_RESTORE_RUNBOOK.md)
- Capacity & log retention policy:
  - [CAPACITY_LOG_RETENTION_POLICY.md](/Users/mustafainan/alpha-quantum/CAPACITY_LOG_RETENTION_POLICY.md)
- Release operasyon checklist:
  - [RELEASE_OPERATION_CHECKLIST.md](/Users/mustafainan/alpha-quantum/RELEASE_OPERATION_CHECKLIST.md)
- API error budget policy:
  - [API_ERROR_BUDGET_POLICY.md](/Users/mustafainan/alpha-quantum/API_ERROR_BUDGET_POLICY.md)

## Project Structure

```text
alpha-quantum/
  app/
    __init__.py
    api.py
    audit_repository.py
    auth_limiter.py
    auth_service.py
    connector_adapters.py
    connector_repository.py
    connector_sync_worker.py
    config.py
    feasibility_repository.py
    finance_repository.py
    macro_data_provider.py
    market_data_provider.py
    market_repository.py
    international_repository.py
    procurement_repository.py
    identity_repository.py
    migration_manager.py
    models.py
    repository.py
    engines/
      company_engine.py
      connector_engine.py
      inventory_engine.py
      finance_engine.py
      global_analysis_engine.py
      international_operations_engine.py
      institution_web_engine.py
      market_data_engine.py
      exchange_source_catalog.py
      feasibility_engine.py
      market_intelligence_engine.py
      procurement_engine.py
      strategic_ecosystem_engine.py
      tender_engine.py
    services.py
  migrations/
    001_permissions_matrix.up.sql
    001_permissions_matrix.down.sql
    002_finance_ledger.up.sql
    002_finance_ledger.down.sql
    003_market_data_cache.up.sql
    003_market_data_cache.down.sql
    004_procurement.up.sql
    004_procurement.down.sql
    005_feasibility_reports.up.sql
    005_feasibility_reports.down.sql
    006_international_projects.up.sql
    006_international_projects.down.sql
    007_user_company_scopes.up.sql
    007_user_company_scopes.down.sql
    008_holdings_onboarding.up.sql
    008_holdings_onboarding.down.sql
    009_connectors_and_sync_queue.up.sql
    009_connectors_and_sync_queue.down.sql
    010_connector_sync_retry_dlq.up.sql
    010_connector_sync_retry_dlq.down.sql
    011_connector_worker_leases.up.sql
    011_connector_worker_leases.down.sql
    012_feasibility_company_scope.up.sql
    012_feasibility_company_scope.down.sql
  main.py
  requirements.txt
  README.md
```

## Run

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Test

```bash
python -m unittest discover -s tests -v
```

## Security Gate

Local security gate run:

```bash
./venv/bin/bandit -c security/bandit.yaml -r app -ll
./venv/bin/pip-audit -r requirements.txt
./venv/bin/python -m unittest discover -s tests -v
./venv/bin/python scripts/security_smoke.py
./venv/bin/python scripts/staging_redis_e2e_smoke.py --redis-url "$AQ_STAGING_REDIS_URL"
./venv/bin/python scripts/staging_redis_toxiproxy_chaos.py
```

One-shot gate helper:

```bash
./scripts/security_gate.sh
```

Operational scripts:

```bash
./scripts/backup_db.sh
./scripts/restore_dry_run.sh ./backups/<backup_file>.db
./venv/bin/python scripts/api_error_budget_report.py --lookback-hours 24 --target-success-ratio 99.0
```

Notes:
- `security/bandit.yaml` contains LOW-risk suppression policy (`B105`, `B311`).
- CI gate is defined at `.github/workflows/security-gate.yml`, provisions Redis + Toxiproxy services, enables `AQ_RUN_STAGING_REDIS_E2E=true` and `AQ_RUN_STAGING_REDIS_CHAOS=true`, and executes `./scripts/security_gate.sh` (6-stage mandatory gate on PR/main/master).
- Manual staging Redis E2E workflow is defined at `.github/workflows/staging-redis-e2e.yml` and expects `staging` environment secret: `AQ_STAGING_REDIS_URL`.
- Manual Redis chaos workflow is defined at `.github/workflows/staging-redis-chaos.yml` (Redis + Toxiproxy services).
- GitHub enforcement checklist is documented at `docs/GITHUB_RELEASE_GATE_CHECKLIST.md`.

## Endpoints

- `GET /` legacy root summary
- `GET /dashboard` dynamic visual dashboard
- `GET /analyze_all` legacy analysis endpoint (original compact response)
- `GET /api/v1/companies` company list
- `GET /api/v1/analysis` analysis output
- `GET /api/v1/summary` dashboard KPI summary
- `GET /api/v1/insights` ranked AI insights
- `GET /api/v1/dashboard-data` aggregated dashboard payload
- `POST /api/v1/auth/login` login, returns bearer token
- `POST /api/v1/auth/refresh` rotate refresh token and issue new access token
- `POST /api/v1/auth/logout` revoke current access token (+ optional refresh revoke)
- `GET /api/v1/auth/me` token validation + profile
- `GET /api/v1/users` admin user list
- `POST /api/v1/users` admin user create
- `PATCH /api/v1/users/{id}` admin user role/active update
- `DELETE /api/v1/users/{id}` admin user delete
- `POST /api/v1/users/{id}/password-rotate` self/admin password rotate
- `GET /api/v1/roles` admin role list
- `POST /api/v1/roles` admin role create
- `PATCH /api/v1/roles/{id}` admin role update
- `DELETE /api/v1/roles/{id}` admin role delete
- `GET /api/v1/permissions` permission catalog
- `GET /api/v1/roles/{id}/permissions` role permission list
- `PUT /api/v1/roles/{id}/permissions` role permission replace
- `GET /api/v1/audit-logs?limit=100` admin audit log read
- `GET /api/v1/admin/migrations/status` migration status
- `POST /api/v1/admin/migrations/apply` apply pending migrations
- `POST /api/v1/admin/migrations/rollback` rollback last migration(s)
- `GET /api/v1/company-engine/overview` company engine snapshot
- `GET /api/v1/inventory-engine/critical` inventory critical feed
- `GET /api/v1/finance-engine/overview` finance engine snapshot
- `POST /api/v1/finance-engine/ledger` create ledger entry
- `GET /api/v1/finance-engine/ledger` list ledger entries
- `GET /api/v1/finance-engine/cashflow` cashflow summary
- `GET /api/v1/finance-engine/forecast` forecast from ledger trends
- `GET /api/v1/market/ohlcv` OHLCV data (DB cached)
- `GET /api/v1/market/analysis` technical analysis (trend, RSI, MACD + signal)
- `GET /api/v1/market/signals` multi-symbol signal cards
- `POST /api/v1/market/refresh` force refresh OHLCV cache
- `GET /api/v1/market/backtest` walk-forward signal strategy backtest (win-rate, return, edge, max drawdown)
- `GET /api/v1/market/sources` exchange source catalog (TR, EU, GLOBAL) for market intelligence adapters
- `POST /api/v1/market/intelligence` market web intelligence + extracted symbols + AI recommendation cards
  - combines `/public-institutions/report` parsing with exchange source profiles and market technical signals
  - decision-support only; no guaranteed return
- `POST /api/v1/procurement/requests` create procurement request (items, strategy, budget, tender constraints)
- `GET /api/v1/procurement/requests` list procurement requests
- `GET /api/v1/procurement/requests/{id}` procurement request detail
- `POST /api/v1/procurement/requests/from-tender` auto-generate procurement plan from tender specs/checklist
- `POST /api/v1/procurement/quotes` submit vendor quote for request items
- `GET /api/v1/procurement/requests/{id}/quotes` list vendor quotes
- `GET /api/v1/procurement/requests/{id}/evaluation` weighted vendor comparison (price/quality/delivery/compliance/vendor score)
- `POST /api/v1/procurement/requests/{id}/purchase-orders/auto` auto-create purchase orders from evaluation
- `GET /api/v1/procurement/requests/{id}/purchase-orders` list generated purchase orders
- `POST /api/v1/feasibility/report` generate and persist professional feasibility report
- `GET /api/v1/feasibility/reports` list generated feasibility reports
- `GET /api/v1/feasibility/reports/{id}` feasibility report detail
- `POST /api/v1/international/projects` create country-based international project development report
- `GET /api/v1/international/projects` list international projects (status/country filter)
- `GET /api/v1/international/projects/{id}` international project detail
- `POST /api/v1/ecosystem/activate` activate integrated enterprise flow (feasibility + international + procurement bootstrap)
- `POST /api/v1/ecosystem/activate/portfolio` activate integrated flow for single company, multi-company, or holding-wide scope from one control point
- `POST /api/v1/holdings` create holding definition
- `GET /api/v1/holdings` list holdings
- `GET /api/v1/holdings/{id}` holding detail with subsidiary onboarding summary
- `POST /api/v1/holdings/{id}/onboard` onboard subsidiaries into holding with readiness scoring
- `POST /api/v1/holdings/onboard/bulk` create holding + onboard subsidiaries in one transaction
- `POST /api/v1/connectors` create integration connector (company scoped)
- `GET /api/v1/connectors` list integration connectors
- `GET /api/v1/connectors/{id}` connector detail
- `POST /api/v1/connectors/canonical/preview` canonical field mapping preview + coverage score
- `POST /api/v1/connectors/{id}/sync-jobs` create prioritized sync job
- `GET /api/v1/connectors/{id}/sync-jobs` list sync jobs for connector
- `GET /api/v1/connectors/sync-jobs` list sync jobs (holding-wide or scope-filtered)
- `POST /api/v1/connectors/sync-jobs/dispatch` claim/dispatch next queued sync job
- `GET /api/v1/connectors/health/summary` connector queue health (queued/processing/completed/failed/dead-letter + avg attempts)
- `GET /api/v1/global/central-banks` global central bank rate panel
- `GET /api/v1/global/world-bank` World Bank indicator panel
- `GET /api/v1/global/report` professional global macro-financial report
- `POST /api/v1/public-institutions/report` public institution web intelligence report (URL-based, term-focused)
  - private/local hosts are blocked by design (SSRF guardrail)
- `POST /api/v1/tender/generate` tender dossier draft from administrative/technical specs (manager/admin)
  - includes professional control checklist, traceability matrix, and readiness summary for auditability
- `POST /api/v1/simulate` mutate demo data (requires `admin` or `manager`)
- `GET /auto_update` legacy mutate endpoint (requires `admin` or `manager`)
- `GET /api/v1/health` service health
  - includes `version` field

## Portfolio Activation Examples

Use an authenticated manager/admin token:

```bash
TOKEN="<ACCESS_TOKEN>"
```

Single company activation:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ecosystem/activate/portfolio \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "scope_mode": "single",
    "project_name_prefix": "AQ Strategic Program",
    "base_country": "TUR",
    "target_countries": ["DEU", "USA"],
    "companies": [
      {
        "company_name": "ABC Holding",
        "sector": "Energy",
        "geography": "TR",
        "objective": "Expand cross-border energy services and procurement governance.",
        "budget_total": 2500000
      }
    ]
  }'
```

Multi-company activation:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ecosystem/activate/portfolio \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "scope_mode": "multi",
    "project_name_prefix": "AQ Multi Program",
    "base_country": "TUR",
    "target_countries": ["DEU", "ARE"],
    "companies": [
      {
        "company_name": "Alpha Manufacturing",
        "sector": "Manufacturing",
        "geography": "TR",
        "objective": "Scale export-driven manufacturing footprint.",
        "budget_total": 1800000
      },
      {
        "company_name": "Beta Logistics",
        "sector": "Logistics",
        "geography": "TR",
        "objective": "Build regional logistics corridors and customs readiness.",
        "budget_total": 1400000
      }
    ]
  }'
```

Holding-wide activation from registered companies:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ecosystem/activate/portfolio \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "scope_mode": "holding",
    "holding_name": "AQ Group",
    "project_name_prefix": "AQ Holding Program",
    "base_country": "TUR",
    "target_countries": ["GBR", "USA", "DEU"],
    "use_registered_companies_when_empty": true,
    "default_sector": "Conglomerate",
    "default_geography": "Global",
    "default_objective": "Coordinate feasibility, international growth, and procurement from one center.",
    "default_budget_total": 3000000,
    "companies": []
  }'
```

## Company Scope Isolation

User profiles now include:
- `company_scopes`: allowed company set (`["*"]` means holding-wide access)
- `scope_mode`: `holding`, `multi`, or `single`

Scope enforcement rules:
- Finance write/read by company name is scope-checked.
- Scoped users (non-`*`) must provide `company` in finance cashflow/forecast/ledger queries.
- Procurement, international, and ecosystem activation endpoints enforce company scope.
- List endpoints for procurement and international are filtered by the caller scope.

Create scoped manager (admin token required):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "scope_manager",
    "password": "ScopeManager123",
    "role": "manager",
    "is_active": true,
    "company_scopes": ["ABC Holding", "Delta Lojistik"]
  }'
```

## Connector Worker (Retry + DLQ)

The connector layer supports both manual dispatch and optional background worker mode.

- Worker polls queued sync jobs (`queued`) at configured interval.
- Failed jobs are re-queued with backoff until `max_attempts` is reached.
- Jobs exceeding retry budget are moved to `dead_letter`.
- Queue health can be observed via `GET /api/v1/connectors/health/summary`.
- Leader lock lease keeps only one active worker (`integration_worker_leases`) in multi-instance mode.

Recommended production profile:

- Keep `AQ_CONNECTOR_WORKER_ENABLED=true` only on one worker replica (or use external queue leader lock).
- Tune `AQ_CONNECTOR_WORKER_POLL_INTERVAL_SECONDS` for throughput vs DB load.
- Tune `AQ_CONNECTOR_WORKER_RETRY_BACKOFF_SECONDS` and `AQ_CONNECTOR_WORKER_MAX_RETRIES` per source reliability.
- Keep `AQ_CONNECTOR_WORKER_LEADER_LOCK_ENABLED=true` in multi-instance deployments.
- Tune `AQ_CONNECTOR_WORKER_LEASE_SECONDS` + `AQ_CONNECTOR_WORKER_HEARTBEAT_SECONDS` based on failover target.

## Demo Users

Available only when `AQ_ENABLE_DEMO_USERS=true`.

- `admin` / `admin123` -> `admin`
- `manager` / `manager123` -> `manager`
- `viewer` / `viewer123` -> `viewer`

Use token:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

Refresh token:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<REFRESH_TOKEN>"}'
```

Dashboard simulate button authorization:

```js
localStorage.setItem("aq_token", "<ACCESS_TOKEN>")
```

Production/static user example:

```bash
AQ_ENABLE_DEMO_USERS=false
AQ_AUTH_USERS=ops:StrongPass123:admin,finance:FinancePass123:manager
```

Default permission matrix:

- `admin`: all permissions
- `manager`: `read_companies`, `run_simulation`, `read_finance`, `write_finance`, `read_market`, `refresh_market`, `read_global_intel`, `read_public_sources`, `prepare_tender_docs`, `read_procurement`, `write_procurement`, `approve_procurement`, `read_feasibility`, `write_feasibility`, `read_international`, `write_international`, `read_holdings`, `manage_holdings`, `read_connectors`, `manage_connectors`
- `viewer`: `read_companies`, `read_finance`, `read_market`, `read_global_intel`, `read_public_sources`, `read_procurement`, `read_feasibility`, `read_international`, `read_holdings`, `read_connectors`

## Environment Variables

- `AQ_APP_NAME` default: `Alpha Quantum`
- `AQ_APP_VERSION` default: `1.0.0`
- `AQ_ENV` default: `development`
- `AQ_LOG_LEVEL` default: `INFO`
- `AQ_ALLOW_ALL_CORS` default: `false`
- `AQ_CORS_ORIGINS` comma-separated list, example: `http://127.0.0.1:8000`
- `AQ_CORS_ALLOW_CREDENTIALS` default: `false`
- `AQ_DATABASE_PATH` default: `alpha_quantum.db`
- `AQ_JWT_SECRET` default: `change-this-secret`
- `AQ_ACCESS_TOKEN_EXPIRE_MINUTES` default: `120`
- `AQ_ENABLE_DEMO_USERS` default: `true` in development, `false` otherwise
- `AQ_AUTH_RATE_LIMIT_WINDOW_SECONDS` default: `60`
- `AQ_AUTH_RATE_LIMIT_MAX_ATTEMPTS` default: `5`
- `AQ_AUTH_RATE_LIMIT_BACKEND` default: `memory` (`memory` or `redis`)
- `AQ_AUTH_RATE_LIMIT_REDIS_URL` default: `redis://127.0.0.1:6379/0`
- `AQ_AUTH_RATE_LIMIT_FAIL_OPEN` default: `true`
- `AQ_AUTH_USERS` optional static users as `username:password:role,username2:password2:role2`
- `AQ_CONNECTOR_WORKER_ENABLED` default: `false`
- `AQ_CONNECTOR_WORKER_POLL_INTERVAL_SECONDS` default: `15`
- `AQ_CONNECTOR_WORKER_RETRY_BACKOFF_SECONDS` default: `60`
- `AQ_CONNECTOR_WORKER_MAX_RETRIES` default: `3`
- `AQ_CONNECTOR_WORKER_LEADER_LOCK_ENABLED` default: `true`
- `AQ_CONNECTOR_WORKER_LEASE_SECONDS` default: `30`
- `AQ_CONNECTOR_WORKER_HEARTBEAT_SECONDS` default: `10`
- `AQ_RUN_STAGING_REDIS_E2E` optional local toggle, `true` adds Redis E2E stage into `./scripts/security_gate.sh`
- `AQ_RUN_STAGING_REDIS_CHAOS` optional local toggle, `true` adds Redis Toxiproxy chaos stage into `./scripts/security_gate.sh`
- `AQ_STAGING_REDIS_URL` optional, used by `scripts/staging_redis_e2e_smoke.py` and optional gate stage
- `AQ_TOXIPROXY_URL` optional, default `http://127.0.0.1:8474`
- `AQ_CHAOS_REDIS_PROXY_NAME` optional, default `aq_redis`
- `AQ_CHAOS_REDIS_PROXY_LISTEN` optional, default `0.0.0.0:8666`
- `AQ_CHAOS_REDIS_UPSTREAM` optional, default `127.0.0.1:6379` (`redis:6379` in CI services)
- `AQ_CHAOS_REDIS_PROXY_URL` optional, default `redis://127.0.0.1:8666/0`
- `AQ_CHAOS_REDIS_SOCKET_TIMEOUT_SECONDS` optional, default `1.0`
- `AQ_MARKET_OFFLINE` optional, `true` forces synthetic market feed (useful for test/offline envs)
- `AQ_MACRO_OFFLINE` optional, `true` forces synthetic macro feed (FRED/World Bank offline mode)
- `AQ_WEB_OFFLINE` optional, `true` forces synthetic public-web snapshot mode (for test/offline envs)

Redis note:
- If `AQ_AUTH_RATE_LIMIT_BACKEND=redis` is enabled, install Redis client package in runtime environment: `pip install redis`.

Staging Redis E2E note:
- `scripts/staging_redis_e2e_smoke.py` validates three scenarios against a real Redis endpoint:
  - distributed login flood across two API instances
  - redis chaos drill (partition simulation, fail-closed behavior, backoff recovery, fail-open policy)
  - connector worker leader-lock failover across two API instances

Staging Redis real-network chaos note:
- `scripts/staging_redis_toxiproxy_chaos.py` validates real network-fault scenarios using Toxiproxy:
  - hard disconnect (`reset_peer`) with fail-closed expectation
  - high latency timeout with fail-closed expectation
  - recovery backoff after toxic removal
  - fail-open policy validation under active fault

Production safety rules:

- `AQ_JWT_SECRET` must not stay as `change-this-secret`
- `AQ_ENABLE_DEMO_USERS` must be `false`
- `AQ_AUTH_USERS` must define at least one user
