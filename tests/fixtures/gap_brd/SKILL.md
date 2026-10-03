---
name: brd
description: >-
  Creates a Business Requirements Document from an approved PRD.
  Use when authoring a BRD after PRD approval.
disable-model-invocation: true
---

# brd — Business Requirements Document creator

Translates an approved PRD into a BRD.

## When to use

- Approved PRD available
- The user asks for a BRD

## When NOT to use

- No PRD yet, send the user to /prd
- Architecture is requested before BRD approval

## Execution contract (mandatory)

**Announce at start:** "Running **/brd** (Business Requirements Document creator)."

### Progress checklist

```
Task Progress:
- [ ] Mode: greenfield / brownfield / integration
- [ ] BRD DRAFT packaged
- [ ] Explicit approval received
- [ ] brd/BRD.md written (post-approval only)
```

### Stop conditions

- Never write finals without explicit approval

### Mini example

```
/brd
Use subskill: workflows then package
@prd/PRD.md
Draft only and wait for approval.
```

## Universal workflow

```
0 Mode detect → new product | existing | feature-on-existing | other
1 Draft package with options and risks
2 EXPLICIT APPROVAL
```

## Approval gate (mandatory)

Silence, partial answers, or implied intent are **not** approval.

## Subskills

| Subskill | File |
|----------|------|
| Workflows | [subskills/workflows.md](subskills/workflows.md) |
| Package | [subskills/package.md](subskills/package.md) |
| Gate | [subskills/gate.md](subskills/gate.md) |

## Enterprise controls

- Deferred items need an owner

## References

- [references/brd-template.md](references/brd-template.md)

## Workflow

Write the final document to brd/BRD.md after approval. Hand off to /architect only after that.

## Done when

- Happy, alternate, exception, and operational workflows covered
- Explicit BRD approval recorded before /architect
