# Skill evaluator

Two commands live in this repo.

- `python -m tse` validates a Trimble agent skill directory: static security, catalog deduplication, and a demo benchmark.
- `python -m skill_evaluator` scores a PRD, BRD, or architecture skill pack with G-Eval and JSON/Markdown schema parsing.

## Install

```powershell
python -m pip install -r requirements.txt
```

## TSE

Point TSE at a skill directory. `validate` runs all three tiers and writes `BENCHMARK.md` in that directory. `scan` runs Tier 1 only. `deduplicate` runs Tier 2 only.

```powershell
python -m tse validate samples\trimble-connect-bcf-manager
python -m tse scan samples\insecure-skill
python -m tse deduplicate samples\my-custom-bcf-helper
python -m tse version
```

`--demo` is the default for `validate`. Live sandbox execution is not implemented, so `--no-demo` stops with exit code 2.

| Exit code | Meaning |
| --- | --- |
| 0 | The requested check passed |
| 1 | A tier failed |
| 2 | `validate --no-demo` |

`scan` exits 1 when Tier 1 finds a violation. `deduplicate` exits 1 for `ERROR` or `REJECTED_DUPLICATE`. `WARNING_DISAMBIGUATE` prints a warning and exits 0.

### Skill directory

```text
my-skill/
  metadata.yaml
  SKILL.md
  tests/eval.json
```

`metadata.yaml` fields:

| Field | Required | Use |
| --- | --- | --- |
| `id` | yes | Catalog id. A match with the mock registry is a version update, not a new skill |
| `name` | yes | Display name |
| `version` | yes | Skill version |
| `author` | yes | Must be a non-empty string |
| `domain` | yes | Product domain used in the similarity text |
| `description` | yes | Compared with catalog descriptions |
| `tid_scopes_required` | yes | Each scope must start with `connect.`, `tekla.`, `projectsight.`, or `geospatial.` |
| `tags` | yes | List of tags included in the similarity text |

`tests/eval.json` is a list of cases, or an object with a `cases` list. Each case has `id`, `category`, `user_prompt`, and `expected_behavior`. Categories used by the demo are `direct_trigger`, `paraphrased_trigger`, `hard_distractor`, and `soft_distractor`.

`expected_behavior.should_trigger` says whether the skill should fire. When it is omitted, trigger categories should fire and distractor categories should not. Optional `demo_control` and `demo_treatment` objects override the built-in demo numbers: `correctness`, `triggered`, `tokens`, `latency_ms`, `tool_reliability`, and `safety`. Scores are 0 to 100. Token and latency values must be greater than zero.

Tier 1 also scans `.py` and `.json` files under the skill directory for secret patterns.

### Tiers

Tiers run in order. Tier 2 and Tier 3 run only after Tier 1 passes. `validate` passes only when Tier 1 is clean, Tier 2 is not `ERROR` or `REJECTED_DUPLICATE`, and Tier 3 passes. A `VERSION_UPDATE` must also keep the Tier 3 composite at or above the previous catalog score.

| Tier | What it checks | Gate |
| --- | --- | --- |
| 1. Static and security | Metadata schema, Trimble ID scope prefixes, hardcoded secrets, and prompt-injection phrases in `SKILL.md` | No violations |
| 2. Catalog deduplication | Same `id` as a registry skill is a version update. Otherwise TF-IDF cosine similarity against the offline mock registry | `REJECTED_DUPLICATE` at 85% or above. `WARNING_DISAMBIGUATE` from 60% up to 85%. `PASSED_UNIQUE` below 60% |
| 3. Demo sandbox | Control versus treatment scores from `tests/eval.json` | Treatment composite at least 80% and uplift at least +15 points |

Tier 3 weights:

| Dimension | Weight |
| --- | ---: |
| Correctness | 35% |
| Discoverability | 25% |
| Efficiency | 20% |
| Tool reliability | 10% |
| Safety | 10% |

Efficiency is the average reduction in tokens and latency from control to treatment. The control composite uses efficiency 0, so uplift is the treatment composite minus that control composite. Demo scores are a fixed simulation. They are not a live model run.

Tier 2 uses a local TF-IDF comparison. If the FastEmbed model `BAAI/bge-small-en-v1.5` is already on disk, that embedding is used instead. TSE does not download a model.

The mock registry contains `trimble-connect-bcf-manager` (previous composite 85.0%), `tekla-drawing-exporter`, and `projectsight-budget-sync`.

`validate` records a SHA-256 of `metadata.yaml`, `SKILL.md`, and `tests/eval.json`. If a parent directory contains `behavior-manifest.json` with `bundleHash`, that value is written as the AGL manifest. Otherwise the report says `N/A`.

### Samples

| Directory | Command | Result |
| --- | --- | --- |
| `samples/trimble-connect-bcf-manager` | `python -m tse validate samples\trimble-connect-bcf-manager` | Passes. Catalog id matches, so Tier 2 is `VERSION_UPDATE`, and Tier 3 stays at or above 85% |
| `samples/my-custom-bcf-helper` | `python -m tse deduplicate samples\my-custom-bcf-helper` | `REJECTED_DUPLICATE`. The description matches the Connect BCF catalog skill |
| `samples/low-uplift-skill` | `python -m tse validate samples\low-uplift-skill` | Tier 2 is `PASSED_UNIQUE`. Tier 3 fails because uplift is under +15 points |
| `samples/insecure-skill` | `python -m tse scan samples\insecure-skill` | Tier 1 fails: `author` is missing, scope `admin.all` is not a Trimble ID prefix, and `SKILL.md` contains a prompt-injection phrase |

`validate` overwrites `BENCHMARK.md` in the skill directory.

## PRD, BRD, and architecture packs

`python -m skill_evaluator` scores a skill pack that writes a PRD, a BRD, or an architecture design. Pass a `SKILL.md`, or that skill file plus the document it produced.

JSON/Markdown schema parsing turns YAML frontmatter and ATX headings into one JSON instance and checks it with JSON Schema draft 2020-12. A failed boolean reports `True was expected`. The schema score is checks passed divided by checks run, scaled to 0–5.

G-Eval fixes the criteria and steps first, collects evidence and gaps, and assigns an integer from 1 to 5. Token probabilities are not used, so the same file always gets the same number.

Skill-pack aspects for a PRD or BRD:

| Aspect | Weight | What it asks |
| --- | ---: | --- |
| Job relevance | 0.20 | The skill stays on PRD or BRD work and names the hand-off |
| Coherence | 0.20 | One procedure, one mode vocabulary, and a draft step tied to the template |
| Output completeness | 0.25 | The pack specifies the fields the document must contain |
| Actionability | 0.15 | Announce line, subskills, example, output path, and an approval question |
| Governance | 0.15 | Silence is not approval, risk tier, and no secrets |
| Fluency and structure | 0.05 | Lean `SKILL.md` and a canonical skill-card title |

An aspect score is 40% schema and 60% G-Eval. A criterion under 3 fails that dimension. Combined 4.0 or higher is acceptable with documented gaps. 4.5 or higher is strong.

Generated PRD and BRD aspects:

| Aspect | Weight | What it asks |
| --- | ---: | --- |
| Contract coverage | 0.25 | Every section required by the skill template is filled in |
| Traceability | 0.20 | Each functional requirement identifier reappears in traceability |
| Coherence | 0.20 | Identifiers are unique, and an approved document has no empty sections |
| Governance | 0.15 | One risk tier, an approval status and date, and no secrets |
| Testability | 0.20 | Each acceptance criterion names an observable outcome |

```powershell
python -m skill_evaluator path\to\SKILL.md --output report.md --json report.json
python -m skill_evaluator path\to\SKILL.md --prd path\to\PRD.md --output report.md --json report.json
python -m skill_evaluator path\to\SKILL.md --brd path\to\BRD.md --output report.md --json report.json
python -m skill_evaluator path\to\SKILL.md --design path\to\design.md --output report.md --json report.json
python -m skill_evaluator --architect-skill path\to\architect\SKILL.md --design-skill path\to\design\SKILL.md --architect-doc path\to\architecture.md --design-doc path\to\design.md
```

On an interactive run, a PRD or BRD skill asks:

1. PRD/BRD skill
2. PRD/BRD skill along with the PRD/BRD document that was generated

Pass `--prd` or `--brd` to select choice 2 without a prompt. The combined score is the average of the skill-pack score and the document score.

An architecture skill asks:

1. Architect and Design skill
2. Architect/Design skill along with the Architecture and design document that was generated

Pass `--design` when one file covers both documents. Pass `--architect-skill` and `--design-skill` when the skills are different files. Pass `--architect-doc` and `--design-doc` when the documents are different files. Every supplied skill and document is scored on all three algorithms, and the combined score is their average.

| Algorithm | What it checks |
| --- | --- |
| Schema parser | Required fields, Markdown syntax, and API formatting |
| G-Eval | Feasibility, security, scalability, tech-stack viability, security boundaries, and business alignment |
| Topological graph validation | Dependency cycles (deadlocks), orphan modules, and coupling density |

`--profile` accepts `auto`, `prd`, `brd`, or `architect`. `--fail-under 4.0` exits 1 when the combined score is below that line.

## Tests

```powershell
python -m pytest
```
