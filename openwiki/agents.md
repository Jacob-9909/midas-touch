# Agents

Midas Touch's conversational assistant (**MidasAdviser**) is a **LangGraph `StateGraph`**, not a free‑running ReAct loop. A front‑end intent classifier decides *which* tools are needed in one shot, the selected tool nodes run **deterministically and in parallel (fan‑out)**, and a single `synthesize` node writes the final answer with **one** LLM call. This cuts the latency/cost of the per‑tool LLM rounds a ReAct agent would incur.

Source: `backend/app/services/agent/`.

---

## Graph Topology

```
START ─► intent (classify) ─► dispatch (conditional fan-out, 0..N tools)
                                   │
        ┌──────────────────────────┴───────────────── tools run in parallel ─────────┐
        │  persona_rag · graph_rag · tax_and_market_lookup      (internal DB / graph) │
        │  product_research · news_research · nts_law_research  (live web search)     │
        │  stock_backtest · stock_quick · cheongyak_lookup      (external API/yfinance)│
        └──────────────────────────┬──────── tool_context accumulates ───────────────┘
                                   ▼
                              synthesize  ─►  END
        (SYSTEM_PROMPT + profile summary + accumulated context → 1 LLM call)
```

If the internal DB already suffices, the intent prompt is instructed **not** to pick live/external tools; if no tool is needed at all, `dispatch` routes straight to `synthesize`.

---

## Nodes (`nodes/`)

Each node is a single file; `graph.py` only imports them and wires the topology (edit node logic in `nodes/`, edit wiring in `graph.py`).

| Node | Class | Role |
|------|-------|------|
| `intent` | router | Classifies which tools to run (structured output, keyword fallback on failure); resets `tool_context`. |
| `routing` | dispatch | Conditional fan‑out edge — sends state to the chosen tool nodes (or directly to `synthesize`). |
| `persona_rag` | internal DB | Peer benchmarking — similar investors' recommended allocation / sector preference (pgvector). |
| `graph_rag` | internal graph | Legal basis / tax‑rate provenance / asset relationships (Neo4j). |
| `tax_lookup` | internal DB | Tax‑saving conditions + current market figures for a given asset. |
| `product_research` | live | Domestic financial‑product current rates/terms (Naver search). |
| `news_research` | live | US/JP/KR base‑rate trend + policy context (web search). |
| `nts_law_research` | live | National Tax Service legal interpretations (latest cases). |
| `stock_backtest` | external | Historical performance / backtest for a ticker (yfinance). |
| `stock_quick` | external | Current technical‑indicator diagnosis (RSI/MACD/MA…). |
| `cheongyak_lookup` | external | Recent/upcoming housing‑subscription notices (Cheongyak Home). |
| `doc_rag` | internal | Korean tax‑law text search via National Tax Service documents (full‑text retrieval). |
| `synthesize` | writer | Single LLM call composing the final answer from `SYSTEM_PROMPT` + profile summary + accumulated `tool_context`. |

Prompts live in `prompts.py`; the shared LLM client in `llm.py`; small helpers in `nodes/_common.py`.

---

## Tools (`tools/`)

Nodes call retrieval tools rather than embedding the I/O inline:

* `persona_rag.py`, `graph_rag.py`, `tax_lookup.py`, `doc_rag.py` — internal DB / Neo4j retrieval and Korean tax‑law document search.
* `_embedding.py` — shared query‑embedding helper (must use the same model that populated `persona_embeddings`).
* `web/` — live search clients: `naver_web.py`, `tavily_search.py`, `nts_law.py`, with shared `_config.py`.

Live tools **degrade gracefully**: with the relevant API key blank they return a clear "not configured" message instead of crashing (see `tests/test_wealth_integration.py`).

---

## State (`state.py`)

`AgentState`:
* `messages` — conversation history (`add_messages` reducer).
* `user_uuid` — **required**.
* `profile_summary` — built on the first turn, reused afterwards.
* `route` — the list of tools intent selected.
* `tool_context` — search context accumulated by the tools, merged with the `merge_tool_context` reducer so parallel fan‑out results combine without conflict.

---

## Persistence (`checkpointer.py`)

Multi‑turn state is persisted to Postgres via LangGraph's **`PostgresSaver`**, keyed by `thread_id` (= `session_id`), over a connection pool. This shares sessions across process restarts and multiple uvicorn workers. The checkpoint tables are owned by **Alembic migrations** (the single source of truth), so `setup()` is intentionally *not* called at runtime.

> **Legacy:** the previous ReAct build (`langchain.agents.create_agent`) is preserved as a commented `[LEGACY]` block in `graph.py` and can be swapped back in by changing the topology.

---

## Where to Look Next

* **[API Reference](/openwiki/api.md)** — the `/chat` and `/chat/stream` (SSE) endpoints that drive the agent.
* **[Data Models](/openwiki/data-models.md)** — `persona_embeddings`, `stock_analysis_memory`, and the LangGraph checkpoint tables.
* **[Pipelines](/openwiki/pipelines.md)** — how the persona/graph/embedding data the tools query is built.
