# Skill evaluator

Scores a skill pack written to generate a PRD, a BRD, or an architecture design. Give it a `SKILL.md` on its own, or give it that skill file plus the document the skill produced.

Two methods from the Grill skill review run on the same pack:

- **JSON/Markdown schema parsing.** YAML frontmatter and ATX headings become one JSON instance. JSON Schema draft 2020-12 checks that instance. A failed boolean reports `True was expected`. The schema score is checks passed divided by checks run, scaled to 0–5.
- **G-Eval.** Criteria and steps are fixed first. The runner collects evidence, notes gaps, and assigns an integer from 1 to 5. This is the form score from that review. Token probabilities are not available, so the same file always gets the same number.

## Aspects

| Aspect | Weight | What it asks |
| --- | ---: | --- |
| Job relevance | 0.20 | The skill stays on PRD or BRD work and names the hand-off |
| Coherence | 0.20 | One procedure, one mode vocabulary, and a draft step tied to the template |
| Output completeness | 0.25 | The pack specifies the fields the document must contain |
| Actionability | 0.15 | Announce line, subskills, example, output path, and an approval question |
| Governance | 0.15 | Silence is not approval, risk tier, and no secrets |
| Fluency and structure | 0.05 | Lean `SKILL.md` and a canonical skill-card title |

An aspect score is 40% schema and 60% G-Eval. The combined score weights the aspect scores. A criterion under 3 fails that dimension. Combined 4.0 or higher is acceptable with documented gaps. 4.5 or higher is strong.

Schema parsing checks that the required boxes exist. G-Eval checks whether those boxes add up to a procedure an agent can follow. A heading can pass the schema and still leave two workflows that disagree.

When a generated PRD is supplied, that document is scored on its own aspects:

| Aspect | Weight | What it asks |
| --- | ---: | --- |
| Contract coverage | 0.25 | Every section required by the skill template is filled in |
| Traceability | 0.20 | Each functional REQ identifier reappears in traceability |
| Coherence | 0.20 | Identifiers are unique, and an approved PRD has no empty sections |
| Governance | 0.15 | One risk tier, an approval status and date, and no secrets |
| Testability | 0.20 | Each acceptance criterion names an observable outcome |

## Run

```powershell
python -m pip install -r requirements.txt
python -m skill_evaluator path\to\SKILL.md --output report.md --json report.json
python -m skill_evaluator path\to\SKILL.md --prd path\to\PRD.md --output report.md --json report.json
python -m skill_evaluator path\to\SKILL.md --brd path\to\BRD.md --output report.md --json report.json
python -m skill_evaluator path\to\SKILL.md --design path\to\design.md --output report.md --json report.json
python -m skill_evaluator --architect-skill path\to\architect\SKILL.md --design-skill path\to\design\SKILL.md --architect-doc path\to\architecture.md --design-doc path\to\design.md
```

On an interactive run, a PRD or BRD skill asks:

1. PRD/BRD skill
2. PRD/BRD skill along with the PRD/BRD document that was generated

Choice 1 scores the skill pack with G-Eval and JSON/Markdown schema parsing. Choice 2 also scores the generated document. Pass `--prd` or `--brd` to select choice 2 without a prompt. The report keeps the skill-pack tables, and adds the generated document tables when a document is supplied. The combined score is the average of the two.

PRD and BRD document aspects are contract coverage, traceability, coherence, governance, and testability.

An architecture skill asks:

1. Architect and Design skill
2. Architect/Design skill along with the Architecture and design document that was generated

Choice 2 asks for the architecture document and the design document. Press Enter on the architecture path when one file covers both, or pass `--design` for that single file. When the skills are different files, pass `--architect-skill` and `--design-skill`. When the documents are different files, pass `--architect-doc` and `--design-doc`.

Every supplied skill and every supplied document is scored on all three algorithms:

| Algorithm | What it checks |
| --- | --- |
| Schema parser | Required fields, Markdown syntax, and API formatting (OpenAPI, operationId, JSON example, security scheme, error model, HTTP path) |
| G-Eval | Feasibility, security, scalability, tech-stack viability, security boundaries, and business alignment |
| Topological graph validation | Dependency cycles (deadlocks), orphan modules, and coupling density |

The combined score is the average of those scores. `--profile` accepts `auto`, `prd`, `brd`, or `architect`. `auto` uses the frontmatter `name`, then the document title. Links that leave the skill directory are listed and are not scored. Files next to `SKILL.md` are part of the pack: subskills, the output template, and `SKILL_CARD.md`.

`--fail-under 4.0` exits 1 when the combined score is below that line. With a generated document, that line is the average of the skill score and the document score.

## Tests

```powershell
python -m pytest
```
