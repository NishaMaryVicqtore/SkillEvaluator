# AGL adoption playbook (Trimble teams)

Five steps to govern behavioral assets without replacing existing CPD SDLC workflows.

## Step 1 — Inventory

List behavioral assets currently outside Git:

- `.cursor/rules/` or legacy `.cursorrules`
- Agent skills on developer machines (`SKILL.md`)
- Chat prompt templates used for PR review or codegen
- MCP server configs granting access to internal APIs

For WorkRide, the inventory is consolidated in this `.ai-governance/` directory.

## Step 2 — Centralize in-repo

Move assets into `.ai-governance/{rules,skills,prompts}`. Remove machine-local copies that diverge from the repository.

Mirror critical rules in `.cursor/rules/` so Cursor loads them automatically—those files should reference `.ai-governance/` as the source of truth.

## Step 3 — Extend pull request review

Require peer review for behavioral asset diffs. Use `PR_REVIEW_CHECKLIST.md`:

- Security alignment (auth, secrets, MCP scopes)
- Consistency with `backend/rules.js` and `TRIMBLE_ID_SETUP.md`
- No conflicting instructions between rule files

## Step 4 — Add CI validation

Integrate `npm run governance:check` into the pipeline (see `.github/workflows/agl-validation.yml`).

Optional: run Promptfoo evaluations from `ci/promptfoo.yaml` when an API key is available for LLM-as-judge tests.

## Step 5 — Trace manifest hash

After merging governance changes:

```bash
npm run governance:manifest
git add behavior-manifest.json
```

Link AI-assisted PRs to the manifest hash so generated code can be traced to the rule set that produced it.

## Measurement (pilot)

Track these metrics during adoption:

| Metric | How to measure |
|--------|----------------|
| Ungoverned local rules | Count repos with `.cursorrules` outside Git |
| AI rework commits | Follow-up commits fixing AI output within 48h of merge |
| Policy violations caught pre-merge | CI `governance:check` failures on PRs |
| Asset reuse | Teams importing shared skills from a central repo |

Report as "early pilot observations" until production-scale data is available.
