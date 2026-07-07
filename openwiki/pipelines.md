# Pipelines Overview

Midas Touch ships three families of **batch pipelines** that run outside the request‑response cycle. They are invoked via the CLI (`uv run python -m <module>`) or through the UI Job Manager (see **Operations**). All pipelines write to the shared PostgreSQL database and, where applicable, to a Neo4j graph.

---

## 1. Data Ingestion (`pipelines/data_ingestion/`)

| Script | Purpose | Key Outputs |
|--------|---------|-------------|
| `fetch_market_data.py` | Pulls equity, fixed‑income, FX, and commodity time‑series from public APIs (Yahoo Finance, FRED, BOK). Handles API‑key validation and normalises data to the `market_snapshots` table schema. | Rows inserted into `shared/database/models/postgres_models.py` → `market_snapshots`.
| `generate_finance_data.py` | Synthesises realistic financial statements and portfolio snapshots for testing and demo. Uses random generators seeded by `numpy`. | Populates `users`, `portfolios`, `portfolio_items`, and related tables.
| `ingest_personas.py` | Imports persona CSV files (`data/augmented_personas.csv`) and creates `PersonaEmbedding` vectors using the configured embedding model. | Fills `persona_embeddings` table (pgvector column).
| `export_csv.py` | Utility to export any SQL table to CSV for external analysis. | CSV files in the `data/exports/` directory.

**How to run** (see Quickstart):
```bash
PYTHONPATH=. uv run python -m pipelines.data_ingestion.fetch_market_data [--backfill]
PYTHONPATH=. uv run python -m pipelines.data_ingestion.ingest_personas --file data/augmented_personas.csv
```

---

## 2. Embedding & Triplet Generation (`pipelines/embedding/`)

These pipelines prepare data for **contrastive fine‑tuning** of LLMs.

* `document_parser.py` – Reads raw PDFs/TXTs/MD/JSONL, splits into token‑level chunks, extracts headings and tables, and stores cleaned passages in `emb_passages`.
* `hard_negative_miner.py` – Implements a Retrieval‑Augmented Generation (RAG) style hard‑negative mining using the **BGE‑M3** embedding model. Produces `(query, positive, negative)` triples.
* `dataset_builder.py` – Combines passages and mined negatives into the final **triplet dataset** (`emb_training_triplets`).
* `pipeline.py` – Orchestrates the end‑to‑end flow: parsing → embedding → mining → dataset creation. Accepts CLI flags to target a single file or the whole `data/raw_documents/` folder.
* `train.py` – Wrapper around a PyTorch training loop (uses `transformers` & `accelerate`) to fine‑tune a language model on the generated triplets.

**Typical usage**:
```bash
# Generate embeddings for a new PDF
PYTHONPATH=. uv run python -m pipelines.embedding.pipeline --file financial_report.pdf

# Train a model on the entire triplet set
PYTHONPATH=. uv run python -m pipelines.embedding.train
```

---

## 3. Knowledge‑Graph Construction (`pipelines/knowledge_graph/`)

The graph captures **entity relationships** extracted from financial documents and public data sources.

* `builder.py` – Incrementally builds Neo4j nodes/edges from the enriched passages (calls `entity_resolution.py` for coreference). Uses the **Neo4j Python driver** and respects existing checkpoints to avoid duplicate work.
* `entity_resolution.py` – Performs fuzzy matching and rule‑based linking of entities (e.g., companies ↔ ticker symbols, tax concepts ↔ legal references).
* `test_rag.py` – End‑to‑end sanity test that runs a sample GraphRAG query against the freshly built graph and asserts that a source sub‑graph is returned.

**Running the builder**:
```bash
PYTHONPATH=. uv run python -m pipelines.knowledge_graph.builder
# Monitor progress via the UI Jobs page or the console logs.
```

---

## Integration with the UI

* The **Job Manager** (`backend/app/services/jobs.py`) exposes `/api/v1/jobs` endpoints that the frontend polls to display progress bars (see `frontend/src/components/JobProgress.tsx`).
* Each pipeline writes a **checkpoint** row to `shared/database/models/postgres_models.py` (`graph_checkpoints`) so that subsequent runs can resume from the last successful step.
* The UI pages (`/graph`, `/finetune`) trigger pipelines via `api.ts` helpers, then render the resulting snapshots or datasets.

---

## Where to Look Next

* **Data Models** – see `/openwiki/data-models.md` for table definitions, including pgvector columns used by embeddings.
* **Agents** – the LangGraph agent uses the analysis memory and the graph‑RAG tool; see `/openwiki/agents.md`.
* **Operations** – detailed instructions for Docker Compose, job lifecycle, and CI/CD are in `/openwiki/operations.md`.
