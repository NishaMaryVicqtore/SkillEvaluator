"""Markdown and JSON reports."""

from __future__ import annotations

import json
from dataclasses import asdict

from skill_evaluator.evaluate import SCHEMA_BLEND, GEVAL_BLEND, Evaluation


def to_markdown(result: Evaluation) -> str:
    parsed = result.parsed
    lines = [
        f"# Skill evaluation — {result.profile.skill_label}",
        "",
        f"**Skill:** `{parsed.name}`  ",
        f"**File:** `{result.skill_path}`  ",
        f"**Evaluated:** {result.evaluated_on.day} {result.evaluated_on.strftime('%B %Y')}  ",
        "**Method:** G-Eval form score (criteria, then steps, then an integer 1–5) combined with JSON Schema draft 2020-12 checks on the parsed Markdown.  ",
        f"**Result:** **{result.combined:.2f} / 5**. {result.verdict}.",
        "",
        "Token log probabilities are not used. The G-Eval number is the integer from the form, the same fallback as the Grill skill review.",
        "",
        "## Score summary",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Combined score (1–5) | {result.combined:.2f} |",
        f"| G-Eval weighted mean (1–5) | {result.geval_weighted:.2f} |",
        f"| G-Eval unweighted mean (1–5) | {result.geval_mean:.2f} |",
        f"| G-Eval normalized mean (0–1) | {(result.geval_mean - 1) / 4:.2f} |",
        f"| Schema checks | {result.schema_passed} / {result.schema_total} ({result.schema_ratio:.2f}) |",
        f"| Schema scaled (0–5) | {result.schema_scaled:.2f} |",
        f"| Schema valid | {'yes' if not result.schema_errors else 'no'} |",
        f"| Verdict | {result.verdict} |",
        "",
        "A criterion under 3 fails that dimension. A combined score of 4.0 or higher is acceptable with documented gaps. 4.5 or higher is strong.",
        "",
        f"Each aspect score is {SCHEMA_BLEND:.0%} schema and {GEVAL_BLEND:.0%} G-Eval. The combined score weights those aspect scores.",
        "",
        "## Aspects",
        "",
        "| Aspect | Weight | G-Eval | Schema | Aspect score |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for aspect in result.aspects:
        lines.append(
            f"| {aspect.label} | {aspect.weight:.2f} | {aspect.geval_score} | "
            f"{aspect.schema_passed}/{aspect.schema_total} | {aspect.combined:.2f} |"
        )
    lines.extend(["", "## G-Eval", ""])
    for item in result.criteria:
        lines.extend(_criterion_block(item))
    lines.extend(["## Schema checks", "", "| # | Assertion | Aspect | Result |", "| --- | --- | --- | --- |"])
    for index, assertion in enumerate(result.assertions, start=1):
        mark = "Pass" if assertion.passed else "Fail"
        lines.append(f"| {index} | {assertion.statement} | {assertion.aspect} | {mark} |")
    failed = [item for item in result.assertions if not item.passed]
    if failed:
        lines.extend(["", "### Failures", ""])
        for assertion in failed:
            lines.extend([f"#### {assertion.statement}", "", assertion.detail, ""])
    if result.schema_errors:
        lines.extend(["## JSON Schema validator", "", "Draft 2020-12 rejected the parsed checks. Each failing boolean reports `True was expected`.", ""])
        for message in result.schema_errors:
            lines.append(f"- `{message}`")
        lines.append("")
    external = result.external_links()
    if external:
        lines.extend(
            [
                "## Links outside the skill pack",
                "",
                "These links are recorded and are not part of the schema score. The score covers files next to the skill.",
                "",
            ]
        )
        for href in external:
            lines.append(f"- `{href}`")
        lines.append("")
    lines.extend(
        [
            "## What this run does not do",
            "",
            "- It does not call a judge model, and it does not weight score-token probabilities.",
            "- It does not run the skill on a sample initiative. A schema can accept a well-formed document that still contradicts itself.",
            "",
        ]
    )
    return "\n".join(lines)


def to_json(result: Evaluation) -> str:
    payload = {
        "skill": result.parsed.name,
        "file": str(result.skill_path),
        "profile": result.profile.id,
        "evaluated_on": result.evaluated_on.isoformat(),
        "combined": round(result.combined, 4),
        "verdict": result.verdict,
        "geval_weighted": round(result.geval_weighted, 4),
        "geval_mean": round(result.geval_mean, 4),
        "schema_passed": result.schema_passed,
        "schema_total": result.schema_total,
        "schema_scaled": round(result.schema_scaled, 4),
        "schema_valid": not result.schema_errors,
        "aspects": [
            {
                "id": aspect.id,
                "label": aspect.label,
                "weight": aspect.weight,
                "geval": aspect.geval_score,
                "schema_passed": aspect.schema_passed,
                "schema_total": aspect.schema_total,
                "score": round(aspect.combined, 4),
            }
            for aspect in result.aspects
        ],
        "criteria": [asdict(item) for item in result.criteria],
        "assertions": [asdict(item) for item in result.assertions],
        "schema_errors": result.schema_errors,
        "external_links": result.external_links(),
    }
    return json.dumps(payload, indent=2) + "\n"


def _criterion_block(item) -> list[str]:
    lines = [
        f"### {item.criterion} — {item.score}",
        "",
        item.requirement,
        "",
        "Steps:",
        "",
        "1. The criterion requires the behavior above.",
        "2. Evidence from the skill pack:",
    ]
    if item.evidence:
        lines.extend(f"   - {point}" for point in item.evidence)
    else:
        lines.append("   - None.")
    lines.append("3. Gaps:")
    if item.gaps:
        lines.extend(f"   - {point}" for point in item.gaps)
    else:
        lines.append("   - None.")
    lines.extend(
        [
            f"4. Score {item.score} / 5. Normalized {(item.normalized):.2f}. Weight {item.weight:.2f}.",
            "",
        ]
    )
    return lines
