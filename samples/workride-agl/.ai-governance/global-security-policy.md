# Global security policy

Agents generating or modifying code in this repository must follow these constraints.

## Secrets and credentials

- Never hard-code API keys, passwords, tokens, or connection strings in source.
- Never commit `.env` or other secret files. Use environment variables and keep templates in `.env.example` only.
- Do not log secrets, Authorization headers, or raw tokens.

## Authentication and session data

- Do not store access tokens or session secrets in `localStorage` or `sessionStorage`.
- Do not add a custom auth bypass, stub login, or "TODO: remove auth" path unless the task explicitly requests a local-only mock and it is clearly isolated.

## Input and output

- Validate and sanitize request bodies and query parameters before use.
- Return consistent JSON errors: `{ "error": "string" }`. Do not leak stack traces or internal paths to clients in default responses.
- Restrict CORS to known origins. Do not enable `origin: "*"` with credentials.

## Dependencies and surface area

- Prefer existing Express middleware over adding new security-sensitive packages without review.
- Do not add file-upload, shell-exec, or eval-based features unless the task requires them and they are scoped safely.
- Do not introduce admin or debug endpoints that skip validation.

## Failure example (ungoverned)

An agent committed a `.env` with a live token and stored that token in `localStorage` for "convenience." That output is rejected.

**Governed outcome:** secrets stay in the environment; tokens stay in memory or httpOnly cookies if auth is added later.
