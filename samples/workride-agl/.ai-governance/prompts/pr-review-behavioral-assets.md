# PR review prompt — behavioral assets

Use this template when reviewing a pull request that changes `.ai-governance/`, Cursor rules, or MCP configuration.

---

You are reviewing behavioral assets for Trimble WorkRide. Application source code is not the only change—AI instructions may affect future code generation across the repo.

## Context files (read first)

- `.ai-governance/rules/architecture-guidelines.md`
- `.ai-governance/rules/trimble-id-auth.md`
- `.ai-governance/rules/booking-policies.md`
- `backend/rules.js`
- `TRIMBLE_ID_SETUP.md`

## Review the diff

For each changed rule, skill, or prompt:

1. **Security:** Does it weaken Trimble ID auth or encourage token storage in localStorage?
2. **Business rules:** Does it conflict with booking cutoffs, cancel window, or no-show policy?
3. **Architecture:** Does it introduce unapproved stack changes?
4. **Conflicts:** Does it contradict another rule file?
5. **Traceability:** Was `behavior-manifest.json` updated?

## Respond with

```markdown
## Behavioral asset review

### Blocking issues
- (list or "none")

### Warnings
- (list or "none")

### Alignment
- Auth: pass / fail
- Booking rules: pass / fail
- Architecture: pass / fail

### Recommendation
- [ ] Approve  [ ] Request changes

### AGL manifest
- Hash in PR: (if provided)
```

---

## Example blocking finding

> Rule change suggests "use email login for production when Trimble ID is unavailable" — **reject**. Production must use Trimble ID per `trimble-id-auth.md`.
