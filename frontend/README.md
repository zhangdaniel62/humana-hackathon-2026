# Claim Assist frontend

React 19 + TypeScript frontend for the Claim Assist backend. Local development
uses Vite's same-origin proxy so the backend's HTTP-only session cookie works
for REST and WebSocket requests without exposing the token to JavaScript.

## Run locally

Start the backend first:

```shell
cd backend
uv sync
uv run python -m src.operations.bootstrap
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Then start the frontend in another terminal:

```shell
cd frontend
pnpm install
pnpm dev
```

Open `http://127.0.0.1:5173`. The Vite server proxies `/api` and `/ws` to the
backend at `127.0.0.1:8000`. For a separately hosted backend, set
`VITE_API_BASE_URL` to its origin and add the frontend's exact origin to
`AUTH_ALLOWED_ORIGINS`; credentialed requests must never use a wildcard origin.
If port 8000 is unavailable, start the backend on another port and launch Vite
with `CLAIM_ASSIST_BACKEND_PROXY_TARGET`, for example
`CLAIM_ASSIST_BACKEND_PROXY_TARGET=http://127.0.0.1:8001 pnpm dev`.

Development accounts are seeded by the backend bootstrap:

| Role | Username | Password | Landing page |
|---|---|---|---|
| Manager | `manager` | `ManagerDemo2026!` | Operations dashboard |
| Customer | `customer` | `CustomerDemo2026!` | Chat and Voice |
| Representative | `rep` | `RepDemo2026!` | Interaction queue |

The representative queue/workspace remains a clearly labeled synthetic demo.
The manager dashboard and customer conversation consume live backend contracts.

## Verify

```shell
pnpm test
pnpm lint
pnpm build
```

The production build may emit the existing advisory that the main JavaScript
chunk exceeds 500 kB; it does not fail the build.
