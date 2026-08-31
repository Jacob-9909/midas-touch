# OpenWiki Quickstart

Welcome to the **Midas Touch** OpenWiki documentation. This guide helps you get the repository up and running, understand its high‑level architecture, and navigate to detailed sections.

---

## 📖 Repository Overview
Midas Touch is a full‑stack, AI‑augmented investment‑assistant platform built with:
- **FastAPI** backend (Python) that exposes a suite of REST endpoints under `/api/v1`.
- **Next.js 16 (App Router)** frontend written in TypeScript + Tailwind, providing interactive UI pages:
  - 💬 **Chat (`/chat`)**: Multi-turn LangGraph agent with deterministic tax calculation and 🛡 5-layer defense proof.
  - 🛡️ **Security (`/security`)**: Fraud detection heuristics & prompt injection defense arena.
  - 🏠 **Cheongyak (`/cheongyak`)**: Korean public housing subscription matching & 84-point calculator.
  - 📊 **Simulator (`/simulator`)**: Privacy-first wealth timeline & compound interest simulator.
  - 🕸️ **Graph (`/graph`, `/query`)**: Neo4j GraphRAG tax law knowledge graph visualizer.
  - 📈 **Stocks (`/stocks`)**: Technical analysis & self-calibration validation loop (`validate_calibration_moat.py`).
- **Data pipelines** for financial data ingestion, embedding generation, and Neo4j knowledge‑graph construction.
- **Shared utilities** (`shared/`) for database access (PostgreSQL + pgvector) and common helpers.
- **LangGraph agents** that orchestrate tool calls, maintain multi‑turn state, and persist conversation checkpoints.

The repository follows a clear separation of concerns, mirroring the directory layout shown in the root `README.md`.

---

## 🎯 3-Minute Quick Evaluation Guide for Judges

For evaluators reviewing Midas Touch, follow these 4 primary validation flows:

| Step | Focus Area | Entrypoint | Validation Check |
|---|---|---|---|
| **1** | **Fraud Defense** | `GET /chat?prefill=...` or `/security` | 10-category scoring, official reporting guide (112/1332), and 🛡 defense proof card appended. |
| **2** | **Zero-Hallucination Tax** | `POST /api/v1/chat` | Deterministic Python calculation (2.5M KRW deduction, 22% rate) with NTS citation footnote. |
| **3** | **Housing & Wealth** | `/cheongyak` & `/simulator` | 84-point subscription score match + compound timeline graph (client-side execution). |
| **4** | **5-Layer Security** | `/security` | 12 attack presets (DAN, prompt leak) blocked by strict tool whitelisting and outer boundaries. |

---

## 🚀 Getting Started
### Prerequisites
- **Python 3.11+** (managed via `uv`)
- **Node.js 20+** for the frontend
- **Docker** (for PostgreSQL, Neo4j, and optional services)
- API keys for LLM providers (set in `.env` – see `.env.example`).

### Installation
```bash
# Install Python dependencies and set up the virtual environment
uv sync

# Install frontend dependencies
(cd frontend && npm install)

# Apply database migrations (PostgreSQL + pgvector + checkpoint tables)
uv run alembic upgrade head
```

### Running the Application
```bash
# Development mode – backend (uvicorn) + frontend (Next.js hot reload)
./dev.sh

# Production mode – build + start
./start.sh
```
The UI will be reachable at `http://localhost:3000` and the API docs at `http://localhost:8000/docs`.

---

## 📚 Documentation Map
Below are the primary OpenWiki pages. Click a link to dive deeper:
- **[Architecture](/openwiki/architecture.md)** – high‑level system diagram, backend vs. frontend responsibilities, and pipeline overview.
- **[API Reference](/openwiki/api.md)** – summary of all FastAPI routes, request/response schemas, and usage examples.
- **[Frontend](/openwiki/frontend.md)** – overview of Next.js pages, component hierarchy, and state handling (user context, theme, SSE chat).
- **[Pipelines](/openwiki/pipelines.md)** – data ingestion, embedding, and knowledge‑graph pipelines; how they are triggered via CLI.
- **[Data Models](/openwiki/data-models.md)** – PostgreSQL schema (tables, pgvector columns) and Neo4j graph model.
- **[Agents](/openwiki/agents.md)** – LangGraph agent graph, nodes, tools, and persistence strategy.
- **[Operations](/openwiki/operations.md)** – async job manager, CLI scripts (`dev.sh`, `start.sh`, `vm.sh`, `db-tunnel.sh`), VM deployment.
- **[Testing](/openwiki/testing.md)** – test suite layout, how to run unit/integration tests.

---

## 🔧 Common Tasks
| Task | Command | Description |
|------|---------|-------------|
| **Run all tests** | `PYTHONPATH=. uv run python -m unittest discover tests -v` | Executes unit, integration, and API tests.
| **Start a data ingestion pipeline** | `PYTHONPATH=. uv run python -m pipelines.data_ingestion.fetch_market_data` | Pulls recent market data via yfinance.
| **Build the knowledge graph** | `PYTHONPATH=. uv run python -m pipelines.knowledge_graph.builder` | Incrementally constructs Neo4j graph snapshots.
| **Trigger a backtest** | `curl -X POST http://localhost:8000/api/v1/stocks/backtest -H "Content-Type: application/json" -d '{...}'` | Runs a single‑stock backtest via the trading service.
| **Start a chat session** | `curl -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" -d '{"session_id":"sess-1","user_uuid":"<uuid>","message":"..."}'` | Opens a multi‑turn conversation with the LangGraph agent.

---

## 👥 Contributing
1. Fork the repository.
2. Create a feature branch.
3. Run `./dev.sh` locally to verify your changes.
4. Add or update tests in the `tests/` directory.
5. Submit a Pull Request.

---

## 📞 Support
- Open an issue on GitHub for bugs or feature requests.
- For usage questions, see the **FAQ** section in the root `README.md` or ask in the project’s discussion board.

---

*All documentation lives under `/openwiki`. Start here, then follow the links to explore each subsystem in depth.*
