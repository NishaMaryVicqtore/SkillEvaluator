# Architectural standards

Agents generating or modifying code must keep the dummy app consistent with this layout.

## Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| App / API | Node.js, Express | Entry: `src/index.js` |
| Static UI | HTML in `src/public/` | Served by Express; no separate frontend toolchain unless approved |
| Port | `4000` by default | Override with `PORT` |

`/src/` is the dummy / AI codegen placeholder. The product application is Trimble WorkRide:

| Layer | Location | Port |
|-------|----------|------|
| WorkRide API | `backend/` (`backend/server.js`) | 3001 |
| WorkRide UI | `frontend/` (Vite/React) | 5173 |

Do not introduce NestJS, a database, or another HTTP server without an explicit architecture change. Do not duplicate WorkRide features inside `/src/`.

## File placement

- Dummy / experimental generation: `/src/` (`src/index.js`, `src/public/`).
- WorkRide API routes and rules: `backend/` (see `rules/architecture-guidelines.md`).
- WorkRide pages: `frontend/src/pages/` with HTTP via `frontend/src/api.js`.
- Do not create a third app tree (`app/`, `server/`) alongside these.


## API design

- REST endpoints live under `/api/`.
- Keep JSON request/response bodies small and explicit.
- Health check remains `GET /api/health` and returns `{ "status": "ok" }` plus optional service metadata.

## Patterns to avoid

- Scattering `fetch` or HTTP clients that assume a different host layout without documenting the change.
- Adding authentication, persistence, or build steps that this dummy app does not need.
- Duplicating policy text into generated code comments instead of following the files in `.ai-governance/`.
