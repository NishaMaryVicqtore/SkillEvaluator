# Trimble ID authentication rules

Agents must not weaken or bypass Trimble ID authentication in production code paths.

## Production requirement

- **Production authentication uses Trimble ID OAuth 2.0** (Authorization Code Grant).
- Setup and callback URLs are documented in `TRIMBLE_ID_SETUP.md` at the repository root.
- Frontend SDK: `@trimble-oss/trimble-id-react` with `useAuth` hook.

## Allowed patterns

- OAuth redirect flow via `/callback` route (`frontend/src/pages/Callback.jsx`)
- Client ID from `VITE_TRIMBLE_CLIENT_ID` environment variable
- Access token provided to API via `setAccessTokenProvider` in `AuthContext.jsx`
- **In-memory token storage** by the Trimble ID SDK (v1.0.3+)

## Development-only exception

- Email-based dummy login on `Login.jsx` is permitted **only** for local development and demos
- Dev login must be clearly separated from production auth paths
- Do not copy dev login patterns into production builds or shared auth utilities

## Forbidden patterns

- Storing access tokens in `localStorage` or `sessionStorage`
- Hard-coding client secrets in frontend code
- Custom JWT issuance replacing Trimble ID for production users
- Skipping token validation on protected API routes
- "Temporary" auth bypass comments left in merged code (`// TODO: remove auth`)

## When adding protected endpoints

1. Verify Trimble ID token on the backend or rely on established middleware patterns
2. Document new scopes or callback URLs in `TRIMBLE_ID_SETUP.md`
3. Update `frontend/.env.example` if new env vars are required

## Concrete failure example (ungoverned)

An agent added a `localStorage.setItem('token', ...)` helper and a `/api/login` stub that bypassed Trimble ID. The UI looked correct but violated Trimble security standards and required rework before release.

**Governed outcome:** Agent follows this file and `AuthContext.jsx`, using Trimble ID SDK token handling only.
