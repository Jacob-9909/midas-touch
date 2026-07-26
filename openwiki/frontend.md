# Frontend Guide

The frontend is a **Next.js 16** application using the new App Router. It provides a single‑page‑application‑style console that talks to the FastAPI backend via the helper library in `frontend/src/lib/api.ts`.

## Project Structure

```
frontend/
├── src/
│   ├── app/               # Top‑level pages (e.g. /chat, /stocks, /cheongyak, /graph, /finetune, /dashboard)
│   │   ├── chat/page.tsx   # Chat UI – uses SSE streaming from `/api/v1/chat/stream`
│   │   ├── stocks/page.tsx # Stock analysis UI – ticker autocomplete, quick‑analysis, backtest, grid‑search, watchlist
│   │   ├── cheongyak/page.tsx # Housing project list & detail modals
│   │   ├── graph/page.tsx   # Interactive Neo4j force‑graph visualisation
│   │   ├── finetune/page.tsx # Document upload & finetuning job monitor
│   │   └── dashboard/[uuid]/page.tsx # User dashboard with portfolio donut chart
│   ├── components/         # Reusable UI building blocks
│   │   ├── NavBar.tsx      # Header with core/engine navigation groups and theme toggle
│   │   ├── JobProgress.tsx # Shows async job progress bars fetched from `/api/v1/jobs`
│   │   ├── GraphView.tsx   # D3‑based force‑graph viewer for Neo4j snapshots
│   │   ├── Reveal.tsx      # Custom animation component used across cards
│   │   └── ui.tsx          # Common primitives: Card, PageTitle, SectionLabel, Spinner, LoadingBlock
│   ├── lib/                # Client‑side utilities
│   │   ├── api.ts          # Thin wrapper around backend REST endpoints; handles JSON, query strings, and SSE token streaming
│   │   ├── theme.tsx       # Dark / light mode state stored in `localStorage`
│   │   ├── toast.tsx       # Global toast notification system
│   │   ├── user-context.tsx # React context providing the selected user UUID and profile (used by all pages)
│   │   └── chat‑seed.ts    # Small helper that injects a seed message when navigating from the analysis UI back to chat
│   └── globals.css        # Tailwind + custom design tokens (accent, ink, line, etc.)
└── package.json           # Depends on React 18, Tailwind, Phosphor icons, and the TypeScript types for the API
```

## State Management

* **User selection** – `useSelectedUser` from `user-context.tsx` stores the currently‑active user (UUID and label). The NavBar displays the selected user and the `ChatPage` uses it to filter chat sessions.
* **Theme** – `useTheme` toggles a CSS class on the `<html>` element; the choice persists across reloads.
* **Chat streaming** – `api.ts`'s `streamChat` opens an `EventSource` to `/api/v1/chat/stream` and appends each token to the assistant bubble in real time.
* **Async jobs** – The `JobProgress` component periodically polls `/api/v1/jobs/{id}` (exposed by the backend job manager) and renders a progress bar and log output.

## Key UI Interactions

| Page | Core Interaction | Backend Endpoint |
|------|------------------|------------------|
| **Chat** | Send user message → stream LLM response (includes Knowledge Panel tab) | `POST /api/v1/chat` / `POST /api/v1/chat/stream` |
| **Stocks** | Select ticker → quick‑analysis view | `GET /api/v1/stocks/quick-analysis?ticker=`
| **Stocks** | View live heatmap data | `GET /api/v1/stocks/heatmap` |
| | Run backtest with risk sliders | `POST /api/v1/stocks/backtest` |
| | Grid‑search for strategy parameters | `POST /api/v1/stocks/grid-search` |
| | Watchlist CRUD | `GET/POST/DELETE /api/v1/stocks/watchlist` |
| **Cheongyak** | List housing projects by kind (with interactive Korean map) | `GET /api/v1/cheongyak/list/{kind}` |
| | View detailed competition / scores | Various `/detail/...` routes |
| **Graph** | Build graph snapshot → visualiser | `POST /api/v1/graph/build/jobs` then `GET /api/v1/graph/snapshot` |
| **Finetune** | Upload document → start pipeline job | `POST /api/v1/finetune/upload` and `POST /api/v1/finetune/jobs` |
| **Dashboard** | Fetch user profile & portfolio | `GET /api/v1/users/{uuid}` |

## How to Extend

* Add a new page: create a folder under `frontend/src/app/<name>/page.tsx` and a route will be automatically generated (Next.js App Router).
* New UI component: place it under `frontend/src/components/` and export from an index if you want to share it.
* New API call: extend `frontend/src/lib/api.ts` with a function that calls the appropriate backend route and returns typed data.

## Development Tips

* Run `./dev.sh` – it starts both the backend (uvicorn) and the frontend (Next.js dev server) with hot‑reload.
* The UI uses **Tailwind JIT**; any changes to classes are reflected instantly.
* For debugging SSE streams, open the browser devtools Network tab and look at the `chat/stream` request – each `data:` line contains a token.

---

**Next steps** – See the **Operations** page for job management and Docker orchestration, and the **Testing** page for how to run the frontend test suite (if present).
