"""Markdown and JSON reports."""

from __future__ import annotations

import json
from dataclasses import asdict

from skill_evaluator.evaluate import SCHEMA_BLEND, GEVAL_BLEND, Evaluation


def to_markdown(result: Evaluation) -> str:
    if result.target in {"architecture", "design", "both"} or result.algorithms or result.design_algorithms:
        return _architect_markdown(result)
    parsed = result.parsed
    title = f"# Skill evaluation — {result.profile.skill_label}"
    if result.artifact is not None:
        kind = "BRD" if result.profile.id == "brd" else "PRD"
        title = f"# Skill and generated {kind} evaluation — {result.profile.skill_label}"
    lines = [
        title,
        "",
        f"**Skill:** `{parsed.name}`  ",
        f"**File:** `{result.skill_path}`  ",
    ]
    if result.artifact is not None:
        lines.append(f"**Generated PRD:** `{result.artifact.path}`  ")
    lines.extend(
        [
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
        ]
    )
    if result.artifact is not None:
        lines.extend(
            [
                f"| Skill pack (1–5) | {result.skill_combined:.2f} |",
                f"| Generated PRD (1–5) | {result.artifact_combined:.2f} |",
            ]
        )
    lines.extend(
        [
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
        (
            f"Each aspect score is {SCHEMA_BLEND:.0%} schema and {GEVAL_BLEND:.0%} G-Eval. "
            + (
                "The combined score is the average of the skill-pack score and the generated PRD score."
                if result.artifact is not None
                else "The combined score weights those aspect scores."
            )
        ),
        "",
        "## Aspects",
        "",
        "| Aspect | Weight | G-Eval | Schema | Aspect score |",
        "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for aspect in result.aspects:
        lines.append(
            f"| {aspect.label} | {aspect.weight:.2f} | {aspect.geval_score} | "
            f"{aspect.schema_passed}/{aspect.schema_total} | {aspect.combined:.2f} |"
        )
    lines.extend(["", "## G-Eval", ""])
    for item in result.criteria:
        lines.extend(_criterion_block(item, "skill pack"))
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
    if result.artifact is not None:
        lines.extend(_artifact_markdown(result))
    lines.extend(
        [
            "## What this run does not do",
            "",
            "- It does not call a judge model, and it does not weight score-token probabilities.",
            (
                f"- It scores the {'BRD' if result.profile.id == 'brd' else 'PRD'} file you supplied. It does not invoke the skill."
                if result.artifact is not None
                else "- It does not run the skill on a sample initiative. A schema can accept a well-formed document that still contradicts itself."
            ),
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
        "mode": _mode(result),
        "target": result.target,
        "skill_combined": round(result.skill_combined, 4),
        "schema_errors": result.schema_errors,
        "external_links": result.external_links(),
        "artifact": _artifact_json(result),
        "algorithms": _algorithms_json(result.algorithms),
        "design_algorithms": _algorithms_json(result.design_algorithms),
        "design_path": result.design_path,
        "subjects": [
            {
                "role": subject.role,
                "file": subject.path,
                "score": round(subject.score, 4),
                "algorithms": _algorithms_json(subject.algorithms),
            }
            for subject in result.subjects
        ],
    }
    return json.dumps(payload, indent=2) + "\n"


def _mode(result: Evaluation) -> str:
    if result.target == "governance":
        return "governance"
    if result.subjects and any(item.role.endswith("document") for item in result.subjects):
        return "skill+design"
    if result.subjects or result.algorithms:
        return "architect"
    if result.artifact is not None and result.profile.id == "brd":
        return "skill+brd"
    if result.artifact is not None:
        return "skill+prd"
    return "skill"


def _architect_markdown(result: Evaluation) -> str:
    subjects = result.subjects or _legacy_subjects(result)
    if result.target == "governance":
        choice = "Rules, skills, policies, evals, and architecture skills"
    else:
        choice = "Architect and design skill"
        if any(item.role.endswith("document") for item in subjects):
            choice = "Architect and design skill with the generated documents"
    lines = [
        f"# {choice} evaluation — {result.profile.skill_label}",
        "",
        f"**Choice:** {choice}  ",
        f"**Skill:** `{result.parsed.name}`  ",
        f"**File:** `{result.skill_path}`  ",
    ]
    for subject in subjects:
        if subject.path != str(result.skill_path):
            lines.append(f"**{subject.role}:** `{subject.path}`  ")
    document_count = sum(1 for item in subjects if item.role.endswith("document"))
    if result.target == "governance":
        blend = "Each rule, skill, policy, eval, and architecture skill is scored on JSON/Markdown schema parsing, G-Eval, and topological graph validation. The combined score is the average of those scores."
    elif document_count:
        blend = "Each skill and each document is scored on all three algorithms. The combined score is the average of those scores."
    elif len(subjects) > 1:
        blend = "Each skill is scored on all three algorithms. The combined score is the average of the skill scores."
    else:
        blend = "This run scores the skill only. The score is the average of schema parsing, G-Eval, and topological graph validation."
    lines.extend(
        [
            f"**Evaluated:** {result.evaluated_on.day} {result.evaluated_on.strftime('%B %Y')}  ",
            "**Method:** JSON/Markdown schema parsing, G-Eval form score, and topological graph validation.  ",
            f"**Result:** **{result.combined:.2f} / 5**. {result.verdict}.",
            "",
            "The G-Eval number is the integer from the rubric. A separate judge model is not called.",
            "",
            "## Score summary",
            "",
            "| Input | Algorithm | Score |",
            "| --- | --- | ---: |",
        ]
    )
    for subject in subjects:
        for algorithm in subject.algorithms:
            lines.append(f"| {subject.role} | {algorithm.label} | {algorithm.score:.2f} |")
        lines.append(f"| {subject.role} score |  | {subject.score:.2f} |")
    lines.extend(
        [
            f"| Combined score (1–5) |  | {result.combined:.2f} |",
            "",
            blend,
            "",
            "A rubric under 3 fails that dimension. Combined 4.0 or higher is acceptable with documented gaps. 4.5 or higher is strong.",
            "",
        ]
    )
    for subject in subjects:
        lines.extend(_aspect_table(subject))
        lines.extend(_algorithm_blocks(subject.algorithms, subject.role))
    lines.extend(
        [
            "## What this run does not do",
            "",
            "- It does not call a judge model, and it does not weight score-token probabilities.",
            "- It does not execute the design or simulate a running system. Deadlocks here are dependency cycles.",
            "",
        ]
    )
    return "\n".join(lines)


def _legacy_subjects(result: Evaluation) -> tuple:
    from skill_evaluator.evaluate import ScoredSubject

    found = []
    if result.algorithms:
        found.append(ScoredSubject("Architect and design skill", str(result.skill_path), result.algorithms))
    if result.design_algorithms:
        found.append(ScoredSubject("Architecture and design document", result.design_path or "", result.design_algorithms))
    return tuple(found)


def _aspect_table(subject) -> list[str]:
    rows = []
    for algorithm in subject.algorithms:
        for item in algorithm.criteria:
            rows.append((item.criterion, item.score))
    if not rows:
        return []
    lines = [
        f"## {subject.role} aspects",
        "",
        "| Aspect | Score |",
        "| --- | ---: |",
    ]
    for name, score in rows:
        lines.append(f"| {name} | {score} |")
    lines.append("")
    return lines


def _algorithm_blocks(algorithms, heading: str) -> list[str]:
    lines: list[str] = []
    for algorithm in algorithms:
        lines.extend([f"## {heading} — {algorithm.label} — {algorithm.score:.2f}", ""])
        if algorithm.checks:
            lines.extend(["| Check | Result |", "| --- | --- |"])
            for check in algorithm.checks:
                mark = "Pass" if check.passed else "Fail"
                lines.append(f"| {check.statement} | {mark} |")
            failed = [check for check in algorithm.checks if not check.passed]
            lines.append("")
            for check in algorithm.checks:
                lines.append(f"- {check.statement}: {check.detail}")
            lines.append("")
        for item in algorithm.criteria:
            lines.extend(_criterion_block(item, algorithm.label.lower()))
    return lines


def _algorithms_json(algorithms) -> list[dict] | None:
    if algorithms is None:
        return None
    payload = []
    for algorithm in algorithms:
        payload.append(
            {
                "id": algorithm.id,
                "label": algorithm.label,
                "score": round(algorithm.score, 4),
                "checks": [asdict(item) for item in algorithm.checks],
                "criteria": [asdict(item) for item in algorithm.criteria],
            }
        )
    return payload


def _artifact_markdown(result: Evaluation) -> list[str]:
    kind = "BRD" if result.profile.id == "brd" else "PRD"
    lines = [
        f"## Generated {kind}",
        "",
        f"The {kind} is checked against the skill template. Schema checks the headings and identifiers. G-Eval checks whether the sections are filled, traceable, consistent, and testable.",
        "",
        f"{kind} score: **{result.artifact_combined:.2f} / 5**. Schema {result.artifact_schema_passed} / {result.artifact_schema_total}.",
        "",
        f"When both inputs are present, the combined score is the average of the skill-pack score and this {kind} score.",
        "",
        "| Aspect | Weight | G-Eval | Schema | Aspect score |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for aspect in result.artifact_aspects:
        lines.append(
            f"| {aspect.label} | {aspect.weight:.2f} | {aspect.geval_score} | "
            f"{aspect.schema_passed}/{aspect.schema_total} | {aspect.combined:.2f} |"
        )
    lines.extend(["", f"### {kind} G-Eval", ""])
    for item in result.artifact.criteria:
        lines.extend(_criterion_block(item, f"generated {kind}"))
    lines.extend([f"### {kind} schema checks", "", "| # | Assertion | Aspect | Result |", "| --- | --- | --- | --- |"])
    for index, assertion in enumerate(result.artifact.assertions, start=1):
        mark = "Pass" if assertion.passed else "Fail"
        lines.append(f"| {index} | {assertion.statement} | {assertion.aspect} | {mark} |")
    failed = [item for item in result.artifact.assertions if not item.passed]
    if failed:
        lines.extend(["", f"#### {kind} failures", ""])
        for assertion in failed:
            lines.extend([f"##### {assertion.statement}", "", assertion.detail, ""])
    if result.artifact.schema_errors:
        lines.extend(["", f"Draft 2020-12 rejected the parsed {kind} checks. Each failing boolean reports `True was expected`.", ""])
        for message in result.artifact.schema_errors:
            lines.append(f"- `{message}`")
        lines.append("")
    return lines


def _artifact_json(result: Evaluation) -> dict | None:
    if result.artifact is None:
        return None
    return {
        "file": result.artifact.path,
        "combined": round(result.artifact_combined, 4),
        "schema_passed": result.artifact_schema_passed,
        "schema_total": result.artifact_schema_total,
        "schema_valid": not result.artifact.schema_errors,
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
            for aspect in result.artifact_aspects
        ],
        "criteria": [asdict(item) for item in result.artifact.criteria],
        "assertions": [asdict(item) for item in result.artifact.assertions],
        "schema_errors": result.artifact.schema_errors,
    }


def _criterion_block(item, source: str) -> list[str]:
    lines = [
        f"### {item.criterion} — {item.score}",
        "",
        item.requirement,
        "",
        "Steps:",
        "",
        "1. The criterion requires the behavior above.",
        f"2. Evidence from the {source}:",
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
