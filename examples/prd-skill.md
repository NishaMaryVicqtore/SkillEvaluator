# Skill evaluation — /prd

**Skill:** `prd`  
**File:** `C:\Users\nvicqto\gs-ai-skillsets\sdlc\common\prd\SKILL.md`  
**Evaluated:** 3 October 2026  
**Method:** G-Eval form score (criteria, then steps, then an integer 1–5) combined with JSON Schema draft 2020-12 checks on the parsed Markdown.  
**Result:** **4.17 / 5**. Acceptable with documented gaps.

Token log probabilities are not used. The G-Eval number is the integer from the form, the same fallback as the Grill skill review.

## Score summary

| Metric | Value |
| --- | --- |
| Combined score (1–5) | 4.17 |
| G-Eval weighted mean (1–5) | 4.00 |
| G-Eval unweighted mean (1–5) | 4.00 |
| G-Eval normalized mean (0–1) | 0.75 |
| Schema checks | 22 / 26 (0.85) |
| Schema scaled (0–5) | 4.23 |
| Schema valid | no |
| Verdict | Acceptable with documented gaps |

A criterion under 3 fails that dimension. A combined score of 4.0 or higher is acceptable with documented gaps. 4.5 or higher is strong.

Each aspect score is 40% schema and 60% G-Eval. The combined score weights those aspect scores.

## Aspects

| Aspect | Weight | G-Eval | Schema | Aspect score |
| --- | ---: | ---: | ---: | ---: |
| Job relevance | 0.20 | 5 | 3/3 | 5.00 |
| Coherence | 0.20 | 3 | 2/3 | 3.13 |
| Output completeness | 0.25 | 4 | 4/4 | 4.40 |
| Actionability | 0.15 | 4 | 5/5 | 4.40 |
| Governance | 0.15 | 4 | 4/5 | 4.00 |
| Fluency and structure | 0.05 | 4 | 4/6 | 3.73 |

## G-Eval

### Job relevance — 5

A skill whose job is to write a Product Requirements Document from a requirements baseline, and to hand that document to /brd or /architect.

Steps:

1. The criterion requires the behavior above.
2. Evidence from the skill pack:
   - The description states the job and includes a Use when trigger.
   - When to use and When NOT to use bound the job.
   - The default output path prd/PRD.md is named.
   - The hand-off names /brd.
3. Gaps:
   - None.
4. Score 5 / 5. Normalized 1.00. Weight 0.20.

### Coherence — 3

One procedure, one mode vocabulary, and a drafting step tied to the output template, so an agent writing a /prd document does not invent the artifact.

Steps:

1. The criterion requires the behavior above.
2. Evidence from the skill pack:
   - Mode labels agree across the sections that declare them.
   - subskills/draft.md points at prd-template.md.
3. Gaps:
   - Universal workflow stops at a design package. Workflow tells the agent to write the document.
4. Score 3 / 5. Normalized 0.50. Weight 0.20.

### Output completeness — 4

The pack specifies every field /prd must put in the document. A localized gap that does not drop a required field scores 4.

Steps:

1. The criterion requires the behavior above.
2. Evidence from the skill pack:
   - objective is specified.
   - scope is specified.
   - functional IDs is specified.
   - non-functional requirements is specified.
   - acceptance criteria is specified.
   - constraints is specified.
   - problem statement is specified.
   - user journeys is specified.
   - traceability is specified.
   - risk tier is specified.
   - approval record is specified.
   - hand-off to /brd is specified.
3. Gaps:
   - No eval scenario is in the pack, so the skill cannot be regression-tested from its own references.
4. Score 4 / 5. Normalized 0.75. Weight 0.25.

### Actionability — 4

The happy path is executable: announce line, subskills, example, output path, and an approval question.

Steps:

1. The criterion requires the behavior above.
2. Evidence from the skill pack:
   - The announce line is exact.
   - The subskill table points at files that exist.
   - A mini example shows the happy path.
   - The happy path names prd/PRD.md.
   - The pack asks for explicit approval.
3. Gaps:
   - The happy path is executable, and an agent still has to choose a procedure or find the template.
4. Score 4 / 5. Normalized 0.75. Weight 0.15.

### Governance — 4

Approval, risk tier, and stop rules are explicit for /prd, and skipped controls carry an owner plus a review date.

Steps:

1. The criterion requires the behavior above.
2. Evidence from the skill pack:
   - Silence is not approval.
   - Drafts come before finals, and finals wait for approval.
   - The risk-tier enum is present.
   - Examples do not contain secret markers.
3. Gaps:
   - Pasted tickets and notes are not marked as untrusted input.
4. Score 4 / 5. Normalized 0.75. Weight 0.15.

### Fluency and structure — 4

The /prd pack is lean, scannable, and uses the canonical skill-card title.

Steps:

1. The criterion requires the behavior above.
2. Evidence from the skill pack:
   - SKILL.md is 117 lines, under the 500-line bar.
   - Depth sits in subskills and references.
3. Gaps:
   - The skill card title is '# SKILL_CARD â€” prd'.
4. Score 4 / 5. Normalized 0.75. Weight 0.05.

## Schema checks

| # | Assertion | Aspect | Result |
| --- | --- | --- | --- |
| 1 | name is kebab-case and at most 64 characters | job_relevance | Pass |
| 2 | description is 40–1024 characters, third person, and contains "Use when" | job_relevance | Pass |
| 3 | disable-model-invocation is true | fluency | Pass |
| 4 | SKILL.md is 1–500 lines | fluency | Pass |
| 5 | Required H2 sections are present | fluency | Pass |
| 6 | Announce line contains `Running **/prd**` | actionability | Pass |
| 7 | Body says silence is not approval | governance | Pass |
| 8 | Risk tier enum low / medium / high / regulated is present | governance | Pass |
| 9 | Hand-off names the next skill | job_relevance | Pass |
| 10 | The Done when section mentions evidence | fluency | Fail |
| 11 | Mini example uses forward slashes | actionability | Pass |
| 12 | No secret markers in the pack | governance | Pass |
| 13 | Checklist records explicit approval | governance | Pass |
| 14 | Checklist drafts before finals | actionability | Pass |
| 15 | Stop condition blocks unapproved finals | governance | Fail |
| 16 | Subskill links exist, match subskills/*.md, and stay one level deep | actionability | Pass |
| 17 | In-pack reference and subskill links resolve | actionability | Pass |
| 18 | SKILL_CARD.md exists | fluency | Pass |
| 19 | SKILL_CARD title is exactly `# SKILL_CARD — prd` with no BOM | fluency | Fail |
| 20 | Checklist, phase 0, and the universal workflow use one mode vocabulary | coherence | Pass |
| 21 | The pack has one procedure for the final document | coherence | Fail |
| 22 | subskills/draft.md points at prd-template.md | coherence | Pass |
| 23 | Output template contains the required headings | completeness | Pass |
| 24 | intake.md lists objective, scope, functional IDs, NFRs, acceptance criteria, and constraints | completeness | Pass |
| 25 | PRD template lists structured NFR categories | completeness | Pass |
| 26 | trace.md keeps REQ-* and NFR-* identifiers | completeness | Pass |

### Failures

#### The Done when section mentions evidence

The word evidence is not in the Done when section.

#### Stop condition blocks unapproved finals

Stop conditions do not mention finals or unapproved writes.

#### SKILL_CARD title is exactly `# SKILL_CARD — prd` with no BOM

Expected # SKILL_CARD — prd. The file starts with a utf-8 bom; the title is mojibake '# skill_card â€” prd'.

#### The pack has one procedure for the final document

Universal workflow stops at a design package. Workflow tells the agent to write the document.

## JSON Schema validator

Draft 2020-12 rejected the parsed checks. Each failing boolean reports `True was expected`.

- `checks.done_when_evidence: True was expected`
- `checks.single_procedure: True was expected`
- `checks.skill_card_title: True was expected`
- `checks.stop_blocks_unapproved_finals: True was expected`

## Links outside the skill pack

These links are recorded and are not part of the schema score. The score covers files next to the skill.

- `../../../EXECUTION-STANDARD.md`
- `../references/enterprise-controls.md`
- `../references/enterprise-controls.md`

## What this run does not do

- It does not call a judge model, and it does not weight score-token probabilities.
- It does not run the skill on a sample initiative. A schema can accept a well-formed document that still contradicts itself.
