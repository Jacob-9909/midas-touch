# Testing

The suite lives in `tests/` and runs on the stdlib `unittest` runner. Everything is invoked with `PYTHONPATH=.` from the repo root.

```bash
# Run everything
PYTHONPATH=. uv run python -m unittest discover tests -v

# Run one file
PYTHONPATH=. uv run python -m unittest tests/test_unit.py -v
```

---

## Suites

Tests split into **offline** (pure logic, deterministic, no network/DB/LLM) and **integration** (require live localhost Postgres/Neo4j and/or an NVIDIA NIM key).

| File | Lines | Needs | Covers |
|------|-------|-------|--------|
| `test_unit.py` | 228 | offline (stubbed deps) | Tax filters, market‑indicator gating, intent short‑circuit, ChatService profile/404, session‑list mapping, GraphRAG query reuse. |
| `test_wealth_integration.py` | 451 | offline (deterministic) | wealth_advisor port: live‑research nodes forced key‑blank → graceful‑degrade message; backtest engine on synthetic prices (no yfinance). |
| `test_backtest.py` | 74 | offline | Backtest risk/cost overlay — stop‑loss, trailing‑stop, cost handling, combined ensemble. |
| `test_allocation.py` | 45 | offline | Allocation‑ratio normalization always sums to exactly 100 (portfolio CHECK constraint). |
| `test_document_parser.py` | 78 | offline | Financial document parser + chunker (pure assertions). |
| `test_api.py` | 102 | **Postgres** | New web‑console routers via FastAPI `TestClient` — read/validate/error (400/404) responses and schema shape only. Does **not** trigger LLM or long batch jobs. |
| `test_agent.py` | 146 | **Postgres + Neo4j + NIM** | Agent & DB‑helper integration. LLM‑dependent tests **skip** when `NVIDIA_API_KEY` is unset. |

---

## Conventions

* **Graceful degradation is tested, not mocked away** — live tools are exercised with keys blanked to assert the "not configured" path (`test_wealth_integration.py`).
* **Integration tests self‑skip** rather than fail when their dependency is absent (e.g. no `NVIDIA_API_KEY` → LLM tests skip). Bring up Docker services and run migrations first (see **[Operations](/openwiki/operations.md)**) for full coverage.
* No pytest, fixtures, or plugins — plain `unittest.TestCase` with `assert*` methods, so any subset runs standalone.

---

## Where to Look Next

* **[Operations](/openwiki/operations.md)** — spin up Postgres/Neo4j and apply migrations before running integration suites.
* **[API Reference](/openwiki/api.md)** — the routes `test_api.py` exercises.
* **[Agents](/openwiki/agents.md)** — the graph `test_agent.py` drives.
