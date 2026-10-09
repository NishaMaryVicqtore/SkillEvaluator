# PR review checklist — behavioral assets

Use this checklist when a pull request changes files under:

- `.ai-governance/`
- `.cursor/rules/`
- MCP server configuration
- Prompt templates used in CI or team workflows

## Security

- [ ] Auth rules require Trimble ID OAuth for production paths (see `rules/trimble-id-auth.md`)
- [ ] No instructions to store access tokens in `localStorage` or commit secrets
- [ ] MCP tool scopes are minimal and documented; no broad production credentials in dev configs

## Business rules

- [ ] Booking/cancel/no-show instructions match `backend/rules.js` (see `rules/booking-policies.md`)
- [ ] No new cutoff times or capacity limits invented in rules without product sign-off

## Architecture

- [ ] Stack constraints respected: Node/Express backend, React/Vite frontend (see `rules/architecture-guidelines.md`)
- [ ] API changes stay consistent with existing `frontend/src/api.js` patterns

## Consistency

- [ ] No conflicting guidance between rule files
- [ ] Cursor rules point to `.ai-governance/` rather than duplicating divergent text

## CI / traceability

- [ ] `npm run governance:check` passes locally
- [ ] `npm run skills:eval` passes for every skill; new or changed tests are listed in the owning skill's `evals.json`
- [ ] `behavior-manifest.json` updated if governance files changed
- [ ] PR description notes `AGL-MANIFEST` hash when AI-generated code depends on new rules

## Reviewer sign-off

| Area | Reviewer | Date |
|------|----------|------|
| Security / auth | | |
| Domain (booking rules) | | |
| Architecture | | |
