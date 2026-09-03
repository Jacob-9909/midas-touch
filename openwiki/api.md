# API Reference

This repository exposes a **FastAPI** server under the `/api/v1` prefix. The API is grouped by functional domain, each with its own router in `backend/app/api/`.

## Common Patterns

* **Path Prefix** – All routes start with `/api/v1`.
* **Response Models** – Pydantic models are used for request validation and response schemas (see the source files).
* **Rate Limiting** – Global IP‑based request throttling is enforced by `backend/app/middleware/rate_limit.py`. See the middleware source for configuration (`RATE_LIMIT`, `RATE_LIMIT_WINDOW`).
* **Authentication** – Auth routes are available (`/api/v1/auth/login`). The UI can obtain a JWT token via login; if `AUTH_ENABLED` is false, the auth layer is bypassed and `user_uuid` may be passed directly.
* **Streaming** – The chat endpoint supports Server‑Sent Events (SSE) for token‑by‑token streaming.

---

## Chat (Agent) Endpoints (`backend/app/api/chat.py`)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | One‑shot chat request. Takes `session_id`, `user_uuid`, `message`. Returns `{session_id, reply}`.
| `POST` | `/chat/stream` | SSE streaming of the final answer (only tokens from the `synthesize` node). Same request shape as `/chat`.
| `GET` | `/chat/sessions` | List recent chat sessions (optionally filter by `user_uuid`). Returns metadata including title and last update.
| `GET` | `/chat/history/{session_id}` | Retrieve stored message history for a session (messages are reconstructed from LangGraph checkpoint state).
| `DELETE` | `/chat/sessions/{session_id}` | Delete a session’s checkpoint data and metadata.

---

## User / Dashboard Endpoints (`backend/app/api/users.py`)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/users` | List all user profiles (basic personal data and portfolio summary).
| `GET` | `/users/{uuid}` | Detailed user profile, including portfolios, risk settings, and persona embeddings.
| `GET` | `/market/snapshots` | Latest market indicator rows (e.g., KOSPI index, interest rates).
| `GET` | `/tax-rules` | Korean tax rule table used by the `tax_and_market_lookup` tool.

---

## Stock Analysis Endpoints (`backend/app/api/stocks.py`)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/stocks/quick-analysis?ticker=` | Returns a snapshot of technical indicators (RSI, MACD, etc.) for the given ticker plus an LLM‑generated outlook. Uses `StockAnalyzer.quick_analysis` and the analysis‑memory cache.
| `GET` | `/stocks/strategies` | Lists available back‑test strategies, their default parameters, and whether they support grid‑search.
| `GET` | `/stocks/ticker-search?q=` | Proxy to Yahoo Finance ticker autocomplete.
| `POST` | `/stocks/backtest` | Run a single back‑test for a ticker/strategy over a date window. Returns performance metrics and trade list.
| `POST` | `/stocks/grid-search` | Perform hyper‑parameter grid search for a strategy; returns the best parameter set and associated returns.
| `POST` | `/stocks/analysis` | Persist a custom analysis result into the `stock_analysis_memory` table.
| `GET` | `/stocks/memory/stats` | Summary statistics of stored analyses (e.g., confidence distribution).
| `GET` | `/stocks/memory/horizon-stats` | Horizon‑based accuracy metrics for the memory layer.
| `POST` | `/stocks/memory/validate` | Validate a new analysis against historic patterns; returns calibrated confidence.
| `POST` | `/stocks/memory/validate-horizons` | Horizon‑level validation of a new analysis.
| `GET` | `/stocks/watchlist` | Retrieve the current user‑specific watchlist.
| `GET` | `/stocks/heatmap` | Retrieve live heatmap data for major tickers (cached 5 min). Returns `source` (data origin) and `last_updated` timestamp.
| `POST` | `/stocks/watchlist` | Add a ticker to the watchlist.
| `DELETE` | `/stocks/watchlist` | Remove a ticker from the watchlist.

---

## Cheongyak (Housing) Endpoints (`backend/app/api/cheongyak.py`)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/cheongyak/list/{kind}` | List housing projects of a given `kind` (e.g., `apt`, `officetel`).
| `GET` | `/cheongyak/detail/{house_manage_no}/{pblanc_no}/housing-types` | Detailed housing‑type breakdown for a specific project.
| `GET` | `/cheongyak/detail/{house_manage_no}/{pblanc_no}/competition` | Competition rate information.
| `GET` | `/cheongyak/detail/{house_manage_no}/{pblanc_no}/scores` | Scoring metrics (e.g., points for special supply).
| `GET` | `/cheongyak/detail/{house_manage_no}/{pblanc_no}/special-supply` | Special‑supply eligibility data.

---

## Tax Rates API (`backend/app/api/tax_rates.py`)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tax-rates/extract` | Extract tax rate proposals from raw text (up to 20k chars). Returns diff against current rates and validation issues. |
| `POST` | `/tax-rates/extract/upload` | Upload a `.txt`, `.md`, or `.pdf` file to extract tax rates. Supports same diff and validation as above. |
| `POST` | `/tax-rates/apply` | Apply a validated tax rate proposal to the overlay for a given year. Returns confirmation and active rates payload. |
| `GET` | `/tax-rates/current` | Retrieve the current effective tax rates for a given year (default 2026), after any overlays. |
| `GET` | `/tax-rates/current?year=2025` | Retrieve rates for a specific year. |

---

## Knowledge Graph & Document RAG Endpoints (`backend/app/api/graph.py`)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/graph/documents` | List currently ingested RAG documents (used by Knowledge Panel). |
| `DELETE` | `/graph/documents/{source}` | Delete a document from RAG (`emb_passages` records and `data/raw_documents/` file). |
| `POST` | `/graph/upload` | Upload a financial document to `data/raw_documents/` for embedding. |
| `POST` | `/graph/ingest/jobs` | Trigger a document ingest job (parse & embed uploaded file). |
| `GET` | `/graph/ingest/jobs/{job_id}` | Get status of a document ingest job. |
| `POST` | `/graph/build/jobs` | Trigger an incremental Neo4j graph build job. |
| `GET` | `/graph/build/jobs` | List active/completed graph‑build jobs. |
| `GET` | `/graph/build/jobs/{id}` | Retrieve job status and logs. |
| `GET` | `/graph/snapshot` | Return a JSON snapshot of Neo4j nodes/edges (used by the UI visualiser). |


---

## GraphRAG Query Endpoint (`backend/app/api/query.py`)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/query` | Submit a natural‑language query. The backend runs a GraphRAG pipeline that retrieves a sub‑graph from Neo4j, fetches relevant embeddings, and returns an LLM‑generated answer with citation snippets.

---

## Research Endpoint (`backend/app/api/research.py`)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/research/rate-briefing` | On‑demand briefing of current US/Japan/Korea benchmark interest rates (uses live web tools).

---

## Health & Root
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Simple health ping, returns a welcome JSON.
| `GET` | `/health` | Checks PostgreSQL connectivity and reports Neo4j URL environment variable.

---

### How to Explore Further

* Source files are located under `backend/app/api/`. Each router file contains the implementation details and Pydantic schemas.
* For request/response examples, run the FastAPI docs (`http://localhost:8000/docs`) after starting the server.
* The OpenWiki pages for **Agents**, **Data Models**, and **Pipelines** explain the underlying services that power many of these endpoints.
