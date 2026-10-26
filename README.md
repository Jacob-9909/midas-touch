# Midas Touch

**English** | [한국어](README.ko.md)

[![CI](https://github.com/Jacob-9909/midas-touch/actions/workflows/ci.yml/badge.svg)](https://github.com/Jacob-9909/midas-touch/actions/workflows/ci.yml)

An AI financial assistant that shows its sources. It checks scam messages, calculates taxes, and answers housing subscription (청약) questions in one conversation, and every answer cites the law or public notice it is based on.

- Demo: https://midas-touch-five.vercel.app (click "체험 계정으로 바로 시작" on the login screen to use a guest account)
- API: https://midas-touch.duckdns.org/health

> This is an information service, not investment or tax advice.

## Features

| Feature | Description |
|---|---|
| Chat assistant (`/chat`) | A LangGraph agent runs only the tools that match the question and streams the answer over SSE |
| Scam message check (`/security`) | Rule-based verdict, response tips, and official report numbers. Includes a prompt-injection defense demo |
| Tax calculation | Rates and deductions are computed by code, not the LLM, with National Tax Service articles attached as sources |
| Housing subscription (`/cheongyak`) | Looks up notices from the public data API, calculates the 84-point score, and compares winning scores per notice |
| Savings simulator (`/simulator`) | Estimates when a target amount is reached. Asset data is computed in the browser only |
| Knowledge graph (`/graph`) | Tax law and subscription documents indexed in Neo4j and pgvector for GraphRAG retrieval |

## Architecture

<p align="center">
  <img src="architecture.svg" alt="Midas Touch architecture" width="100%" />
</p>

```
Browser ── Vercel (Next.js) ── FastAPI + LangGraph ──┬─ PostgreSQL (pgvector)
                                (Oracle Cloud VM)    └─ Neo4j
```

## Tech Stack

- Frontend: Next.js 16, React 19, TypeScript, Tailwind CSS
- Backend: Python 3.12, FastAPI, LangGraph, Alembic
- Data: PostgreSQL 17 (pgvector), Neo4j 5
- LLM: NVIDIA NIM (`gemma-4-31b-it`, `bge-m3`)
- Infra: Vercel, Oracle Cloud VM (systemd, Caddy), GitHub Actions

## Getting Started

```bash
uv sync
(cd frontend && npm install)
uv run alembic upgrade head
./dev.sh          # backend :8000, frontend :3000
```

See `.env.example` for environment variables. Tests and lint:

```bash
uv run pytest
uv run ruff check .
```

## Project Structure

```
backend/     FastAPI routers and LangGraph agents
frontend/    Next.js web console
pipelines/   Data collection, document embedding, graph builder
shared/      DB clients, rate limiter
infra/       Caddy, systemd, auto-deploy scripts
tests/       pytest
```

## Docs (Korean)

- [Architecture](openwiki/architecture.md)
- [Agents](openwiki/agents.md)
- [API](openwiki/api.md)
- [Deploy runbook](docs/deploy-runbook.md)
