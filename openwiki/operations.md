# Operations

How to run, expose, and operate Midas Touch locally. There is **no auth layer** — the web console assumes a trusted local/single‑operator context.

---

## Backing Services (Docker Compose)

For production deployments on the Oracle VM, the backend and databases are run as native systemd services (see `infra/midas-backend.service` and the related unit files). Caddy is used as the reverse‑proxy with automatic TLS (see `infra/Caddyfile`).

To start the services on the VM use:

```bash
sudo systemctl enable --now midas-backend
# Ensure PostgreSQL and Neo4j systemd units are enabled and started as described in the deployment runbook.
```

Local development continues to use the single‑file command shown earlier.


`infra/docker-compose.yml` provisions the two stateful dependencies:

| Service | Image | Ports | Notes |
|---------|-------|-------|-------|
| `postgres` | `pgvector/pgvector:pg16` | `5432` | App DB + pgvector embeddings + LangGraph checkpoints. Volume `postgres_data`. |
| `neo4j` | `neo4j:5.26-community` | `7474` (HTTP), `7687` (Bolt) | Knowledge graph, with the `apoc` plugin. Volumes `neo4j_data` / `neo4j_import` / `neo4j_plugins`. |

Credentials are read from `.env` (`POSTGRES_*`, `NEO4J_USERNAME/PASSWORD`). Bring them up with:

```bash
docker compose -f infra/docker-compose.yml up -d
uv run alembic upgrade head   # apply schema + checkpoint tables
```

---

## Launchers

| Script | Purpose | Backend | Frontend |
|--------|---------|---------|----------|
| `./dev.sh` | Local development | `uvicorn … --reload` (:8000) | `next dev` HMR (:3000) |
| `./start.sh` | Production‑style run | `uvicorn … --workers N` (no reload) | `next build` → `next start` |
| `./expose.sh` | Public tunnel | runs `start.sh` … | … + `ngrok http 3000` |

All three fix the project root, trap `Ctrl+C` to tear down the whole process group, and accept a `backend` / `frontend` argument to run just one side.

```bash
./dev.sh                 # backend + frontend
./dev.sh backend         # backend only
SKIP_BUILD=1 ./start.sh  # reuse existing frontend .next build
```

**Environment knobs:** `BACKEND_HOST`, `BACKEND_PORT` (8000), `BACKEND_WORKERS` (1), `FRONTEND_PORT` (3000).

> ⚠️ **Keep `BACKEND_WORKERS=1`.** The Job Manager keeps per‑worker in‑memory state, so job progress is only consistent with a single worker. Multi‑turn chat is unaffected (checkpoints are shared in Postgres).

### Exposing externally

`expose.sh` waits for `:3000` to return `200`, then starts an ngrok tunnel and prints the public URL (ngrok dashboard at `http://localhost:4040`). **Use production build behind the tunnel, never `dev.sh`** — dev's HMR WebSocket dies on free ngrok and hydration never completes.

---

## Async Job Manager

`backend/app/services/jobs.py` runs long batch pipelines (embedding fine‑tune‑set generation, knowledge‑graph build) by launching the existing CLI modules via `asyncio.create_subprocess_exec` and buffering stdout. The frontend polls by `job_id` for status / progress / log tail.

* **Progress** is estimated from `[n/m]` stage markers in pipeline logs (`_STAGE_RE`), avoiding confusion with inline percentages like `coverage=83.0%`.
* **Persistence** — each job's metadata + recent logs (last 500 lines) are written to `data/jobs/<job_id>.json`, surviving restarts. In‑flight subprocess handles are not resumed after a crash.
* `Job.kind` is `"finetune"` or `"graph_build"`; status is `running | succeeded | failed`.

Frontend surface: `frontend/src/components/JobProgress.tsx`, driven from the `/graph` and `/finetune` pages.

---

## Migrations

Alembic (`alembic.ini`, migrations under `shared/database/`) is the **single source of truth** for all schema, including the LangGraph checkpoint tables — do not call `PostgresSaver.setup()` at runtime. `stock_analysis_memory` is the one exception: it self‑creates via `CREATE TABLE IF NOT EXISTS` on first use.

```bash
uv run alembic upgrade head          # apply latest
uv run alembic revision --autogenerate -m "msg"   # new migration
```

---

## Where to Look Next

* **[Pipelines](/openwiki/pipelines.md)** — the CLI batch jobs the Job Manager wraps.
* **[Testing](/openwiki/testing.md)** — which suites need live Postgres/Neo4j/NIM and which run fully offline.
* **[Data Models](/openwiki/data-models.md)** — the schema Alembic manages.
