# Architecture guidelines — Trimble WorkRide

Agents generating or modifying WorkRide code must follow these constraints.

## Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Backend API | Node.js, Express | Entry: `backend/server.js`; business rules in `backend/rules.js` |
| Data store | JSON file (`backend/data/store.json`) | Do not introduce a database without an approved architecture change |
| Frontend | React 18, Vite, React Router | Pages in `frontend/src/pages/` |
| Auth | Trimble ID (`@trimble-oss/trimble-id-react`) | See `rules/trimble-id-auth.md` |

## API design

- REST endpoints under `/api/` proxied from Vite dev server
- Use `frontend/src/api.js` for HTTP calls; do not scatter `fetch` across components
- Return JSON with consistent error shapes: `{ error: string }` for failures

## File placement

- New API routes and handlers: `backend/server.js` or dedicated modules imported by it
- New React pages: `frontend/src/pages/` with routes in `frontend/src/App.jsx`
- Environment variables: `frontend/.env` (never commit secrets; use `.env.example` for templates)

## Patterns to avoid

- Do not add a second auth system (custom JWT, session cookies) for production
- Do not duplicate booking cutoff logic in the frontend without matching `backend/rules.js`
- Do not add heavyweight frameworks (NestJS, Redux) without team approval

## Reference implementations

- Booking flow: `frontend/src/pages/Book.jsx` + booking endpoints in `backend/server.js`
- Auth flow: `frontend/src/context/AuthContext.jsx`, `frontend/src/pages/Callback.jsx`
