# Skill evaluator

Scores a skill pack written to generate a PRD or a BRD. Give it a `SKILL.md`. It reads that file and the Markdown beside it, then returns a score for each aspect.

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

## Run

```powershell
python -m pip install -r requirements.txt
python -m skill_evaluator path\to\SKILL.md --output report.md --json report.json
```

`--profile` accepts `auto`, `prd`, or `brd`. `auto` uses the frontmatter `name`, then the document title. Links that leave the skill directory are listed and are not scored. Files next to `SKILL.md` are part of the pack: subskills, the output template, and `SKILL_CARD.md`.

`--fail-under 4.0` exits 1 when the combined score is below that line.

## Tests

```powershell
python -m pytest
```
