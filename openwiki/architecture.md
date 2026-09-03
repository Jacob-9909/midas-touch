# Architecture Overview

Midas Touch is organized around **four major technical domains** that align with business capabilities:

| Domain | Purpose | Key Modules | Primary Language |
|--------|---------|-------------|-----------------|
| **Backend API** | Real‑time data services, multi‑turn LLM‑driven agent, trading analysis, user/portfolio management. | `backend/app/main.py`, `backend/app/api/*`, `backend/app/services/*` | Python (FastAPI, LangGraph) |
| **Frontend UI** | Interactive console for chat, stock analysis, cheongyak (Korean housing), graph visualisation, finetuning pipelines. | `frontend/src/app/*/page.tsx`, `frontend/src/components/*`, `frontend/src/lib/*` | TypeScript (Next.js 16, Tailwind) |
| **Data Pipelines** | Batch jobs that ingest raw financial data, generate embeddings, and build a Neo4j knowledge graph. | `pipelines/data_ingestion/*`, `pipelines/embedding/*`, `pipelines/knowledge_graph/*` | Python (yfinance, LangChain, Neo4j driver) |
| **Shared Core** | Database connectors, ORM models, utility helpers used by all layers. | `shared/database/*`, `shared/utils/*` | Python |

## Backend Architecture

* **Entry point** – `backend/app/main.py` creates a FastAPI app, registers routers (`auth`, `chat`, `users`, `tax_rates`, `graph`, `query`, `stocks`, `cheongyak`, `research`). It also starts a background validation loop that periodically scores the analysis memory.
* **API Routers** – each router lives under `backend/app/api/` and groups related endpoints (e.g., `stocks.py` exposes quick‑analysis, backtest, grid‑search, and memory statistics). Routes are mounted under `/api/v1`.
* **Services** – business logic is encapsulated in `backend/app/services/`:
  * `agent/` – LangGraph state graph, node definitions, tool implementations, persistence via `PostgresSaver`.
  * `trading/` – `stock_analyzer.py` for technical indicators, `ai_analysis.py` for LLM commentary, `analysis_memory.py` for storing past analysis results.
  * `cheongyak/` – thin wrapper around the public 청약홈 API.
* **Persistence** – PostgreSQL (via `shared/database/connector.py` and repositories) stores users, portfolios, tax rules, chat sessions, and vector embeddings (pgvector). Neo4j holds the knowledge graph used by `graph_rag` tools.
* **Background Jobs** – `backend/app/services/jobs.py` provides an async job manager used by the UI to launch long‑running pipelines; job progress is persisted in the DB and exposed via `/jobs` endpoints.

## Frontend Architecture

* **Next.js App Router** – each top‑level page lives in `frontend/src/app/<name>/page.tsx` (e.g., `/chat`, `/stocks`). Pages compose shared UI components.
* **Component Library** – `frontend/src/components/` contains reusable UI building blocks: `NavBar`, `JobProgress`, `GraphView`, `Reveal` animations, and skeleton loaders.
* **State & Utilities** – `frontend/src/lib/` provides:
  * `api.ts` – thin wrapper around the backend API with automatic JWT handling and SSE streaming for chat.
  * `user-context.tsx` – React context that stores the selected user UUID and profile, shared across pages.
  * `theme.tsx` – dark/light mode toggle.
  * `toast.tsx` – global toast notifications.
  * `chat‑seed.ts` – seed data for the chat UI.
* **SSR / CSR** – Most pages are client‑side rendered (CSR) for interactive charts and real‑time updates; the root layout handles auth‑less navigation.

## Data Pipelines

* **Ingestion (`pipelines/data_ingestion/`)** – scripts fetch market data via yfinance, scrape Korean tax/legislation sources, and load synthetic finance data (`generate_finance_data.py`). Outputs are written to the PostgreSQL tables.
* **Embedding (`pipelines/embedding/`)** – generates token‑level embeddings using the configured LLM embedding model (default `BAAI/bge-m3`). The pipeline builds a triplet dataset for contrastive fine‑tuning.
* **Knowledge Graph (`pipelines/knowledge_graph/`)** – incremental Neo4j builder (`builder.py`) parses enriched documents, resolves entities (`entity_resolution.py`), and stores nodes/edges. A test harness (`test_rag.py`) verifies GraphRAG queries.
* **CLI Integration** – each pipeline can be invoked via `uv run python -m <module>` or through the UI job manager (see **Operations** docs).

## Why This Layout?

* **Separation of Concerns** – Backend, frontend, pipelines, and shared utilities are isolated to allow independent scaling (e.g., the backend can be containerised separately from the UI).
* **Single‑Source Truth** – All business rules (tax calculation, portfolio allocation) live in the backend services and DB migrations; the UI merely consumes the API.
* **Extensibility** – Adding a new agent tool or pipeline only requires updating the respective `services/agent/tools/` or `pipelines/` directory without touching other layers.
* **Observability** – Background jobs emit progress logs stored in the DB, enabling the UI to poll `/jobs` endpoints for real‑time feedback.

---

**Next steps** – Explore the detailed sections:
- **[API Reference](/openwiki/api.md)** for endpoint signatures.
- **[Frontend Guide](/openwiki/frontend.md)** for UI component hierarchy.
- **[Pipelines](/openwiki/pipelines.md)** for batch processing workflows.
- **[Data Models](/openwiki/data-models.md)** for schema details.
- **[Agents](/openwiki/agents.md)** for LangGraph state graph design.
- **[Operations](/openwiki/operations.md)** for job management and deployment.
- **[Testing](/openwiki/testing.md)** for running the test suite.
