"""Crisp Metric / Value report for a PRD skill, architecture skills, and rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from skill_evaluator.architect_eval import AlgorithmScore, score_architect_skill
from skill_evaluator.evaluate import evaluate
from skill_evaluator.geval import CriterionScore
from skill_evaluator.governance_eval import score_governance
from skill_evaluator.parse import parse_skill

G_EVAL = "G-Eval"
JSON_SCHEMA = "JSON Schema"
GRAPH = "Topological Graph Validation"
_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_ROOT = Path(__file__).resolve().parents[1]
_CURSOR_PRD = Path(r"C:\Users\nvicqto\.cursor\skills\prd\SKILL.md")
_CURSOR_ARCHITECT = Path(r"C:\Users\nvicqto\.cursor\skills\architect\SKILL.md")


@dataclass(frozen=True)
class _Finding:
    where: str
    metric: str
    gap: str
    solution: str


@dataclass(frozen=True)
class _Item:
    title: str
    group: str
    metrics: tuple[tuple[str, str], ...]
    findings: tuple[_Finding, ...] = ()

    @property
    def combined(self) -> float:
        for metric, value in self.metrics:
            if metric == "Combined":
                return float(value)
        return 0.0


def suite_report(
    governance: Path | str | None = None,
    prd_skill: Path | str | None = None,
    architect_skill: Path | str | None = None,
    project: Path | str | None = None,
) -> str:
    """Score the PRD skill, architecture skills, and rules, then render Metric / Value tables."""
    governance_path = Path(governance) if governance else _ROOT / "samples" / "workride-agl"
    prd_path = Path(prd_skill) if prd_skill else _default_prd()
    architect_path = Path(architect_skill) if architect_skill else (_CURSOR_ARCHITECT if _CURSOR_ARCHITECT.is_file() else None)
    scored = score_governance(governance_path, project_path=Path(project) if project else None)
    groups = (
        ("PRD skill", (_prd_item(prd_path),)),
        ("Architecture skills", tuple(_architecture_items(architect_path, scored))),
        ("Rules", tuple(_items_with_prefix(scored, "Rule —"))),
    )
    return _render(groups)


def crisp_evaluation_report(result) -> str:
    """Render one evaluation as Metric / Value tables."""
    if result.subjects:
        items = tuple(_item_from_algorithms(title, subject.role, subject.algorithms) for subject in result.subjects)
        title = "Rules, skills, policies, evals, and architecture skills" if result.target == "governance" else result.profile.skill_label
        return _render(((title, items),))
    graph = score_pack_graph(result.parsed.files)
    algorithms = (
        AlgorithmScore("geval", G_EVAL, result.geval_weighted, (), tuple(result.criteria)),
        AlgorithmScore("schema", JSON_SCHEMA, result.schema_scaled, tuple(result.assertions), ()),
        graph,
    )
    title = "PRD skill" if result.profile.id == "prd" else result.profile.skill_label
    return _render(((title, (_item_from_algorithms(title, result.parsed.name, algorithms),)),))


def score_pack_graph(files: dict[str, str]) -> AlgorithmScore:
    """Score file-to-file links in a skill pack as a dependency graph."""
    graph = {name: set() for name in files}
    for name, text in files.items():
        for href in _LINK.findall(text):
            target = href.strip().split("#", 1)[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = _normalize(str(Path(name).parent / target.replace("\\", "/")))
            if resolved in graph and resolved != name:
                graph[name].add(resolved)
    incoming = {name: 0 for name in graph}
    for targets in graph.values():
        for target in targets:
            incoming[target] = incoming.get(target, 0) + 1
    cycles = _cycles(graph)
    orphans = [name for name, targets in graph.items() if not targets and incoming.get(name, 0) == 0]
    fan_out = max((len(targets) for targets in graph.values()), default=0)
    deadlock = 1 if cycles else 5
    if not graph:
        orphan = 1
    elif not orphans:
        orphan = 5
    elif len(orphans) == 1:
        orphan = 3
    else:
        orphan = 1
    if fan_out <= 4:
        coupling = 5
    elif fan_out <= 8:
        coupling = 4
    elif fan_out <= 12:
        coupling = 3
    else:
        coupling = 2
    criteria = (
        CriterionScore(
            "deadlock",
            "Deadlocks",
            1 / 3,
            deadlock,
            "Pack links do not form a cycle.",
            ("No citation cycle.",) if deadlock == 5 else (),
            () if deadlock == 5 else ("A citation cycle is present.",),
        ),
        CriterionScore(
            "orphan",
            "Orphan modules",
            1 / 3,
            orphan,
            "Every pack file is linked.",
            ("Every pack file is linked or links onward.",) if orphan == 5 else (),
            () if orphan == 5 else (f"Unlinked files: {', '.join(orphans)}.",),
        ),
        CriterionScore(
            "coupling",
            "Coupling density",
            1 / 3,
            coupling,
            "Files cite a small set of other files.",
            (f"Highest fan-out is {fan_out}.",),
            () if coupling >= 4 else (f"Highest fan-out is {fan_out}.",),
        ),
    )
    score = sum(item.score for item in criteria) / len(criteria)
    return AlgorithmScore("structure", GRAPH, score, (), criteria)


def _prd_item(path: Path) -> _Item:
    result = evaluate(path)
    graph = score_pack_graph(result.parsed.files)
    algorithms = (
        AlgorithmScore("geval", G_EVAL, result.geval_weighted, (), tuple(result.criteria)),
        AlgorithmScore("schema", JSON_SCHEMA, result.schema_scaled, tuple(result.assertions), ()),
        graph,
    )
    return _item_from_algorithms("PRD skill", result.parsed.name, algorithms)


def _architecture_items(architect_skill: Path | None, scored) -> list[_Item]:
    items: list[_Item] = []
    if architect_skill is not None and architect_skill.is_file():
        parsed = parse_skill(architect_skill)
        items.append(_item_from_algorithms("Architecture skills", parsed.name, score_architect_skill(parsed)))
    items.extend(_items_with_prefix(scored, "Architecture skill —"))
    return items


def _items_with_prefix(scored, prefix: str) -> list[_Item]:
    return [
        _item_from_algorithms(prefix.split(" —", 1)[0], row.role.removeprefix(prefix).strip(), row.algorithms)
        for row in scored
        if row.role.startswith(prefix)
    ]


def _item_from_algorithms(group: str, title: str, algorithms: tuple[AlgorithmScore, ...]) -> _Item:
    rows: list[tuple[str, str]] = []
    findings: list[_Finding] = []
    where = f"{group} / {title}"
    order = {"geval": 0, "schema": 1, "structure": 2}
    for algorithm in sorted(algorithms, key=lambda item: order.get(item.id, 9)):
        rows.append((_metric_name(algorithm), f"{algorithm.score:.2f}"))
        for criterion in algorithm.criteria:
            rows.append((criterion.criterion, str(criterion.score)))
            if criterion.score < 5 and criterion.gaps:
                gap = "; ".join(criterion.gaps)
                findings.append(_Finding(where, criterion.criterion, gap, _solution(criterion.id, criterion.criterion, gap)))
        if algorithm.id == "schema":
            failed = [check for check in algorithm.checks if not check.passed]
            if algorithm.checks:
                rows.append(("Schema checks", f"{len(algorithm.checks) - len(failed)} / {len(algorithm.checks)}"))
            for check in failed:
                gap = check.detail or check.statement
                findings.append(_Finding(where, "JSON Schema", f"{check.statement}. {gap}", _schema_solution(check.statement, gap)))
    combined = sum(algorithm.score for algorithm in algorithms) / len(algorithms)
    rows.append(("Combined", f"{combined:.2f}"))
    return _Item(title, group, tuple(rows), tuple(findings))


def _metric_name(algorithm: AlgorithmScore) -> str:
    return {"geval": G_EVAL, "schema": JSON_SCHEMA, "structure": GRAPH}.get(algorithm.id, algorithm.label)


def _render(groups: tuple[tuple[str, tuple[_Item, ...] | list[_Item]], ...]) -> str:
    lines = ["# Evaluation report", "", "| Metric | Value |", "| --- | ---: |"]
    group_scores = []
    for title, items in groups:
        if not items:
            continue
        score = sum(item.combined for item in items) / len(items)
        group_scores.append(score)
        lines.append(f"| {title} | {score:.2f} |")
    overall = sum(group_scores) / len(group_scores) if group_scores else 0.0
    lines.extend([f"| Combined | {overall:.2f} |", ""])
    lines.append("Each score is 1–5. Combined is the average of G-Eval, JSON Schema, and Topological Graph Validation.")
    lines.append("")
    for title, items in groups:
        if not items:
            continue
        lines.extend([f"## {title}", ""])
        for item in items:
            lines.extend([f"### {item.title}", "", "| Metric | Value |", "| --- | ---: |"])
            for metric, value in item.metrics:
                lines.append(f"| {metric} | {value} |")
            lines.append("")
    lines.extend(_gap_section(groups))
    return "\n".join(lines)


def _gap_section(groups: tuple[tuple[str, tuple[_Item, ...] | list[_Item]], ...]) -> list[str]:
    findings = [finding for _, items in groups for item in items for finding in item.findings]
    lines = ["## Gaps and solutions", ""]
    if not findings:
        lines.extend(["No gaps. Every scored metric is 5.", ""])
        return lines
    lines.extend(["| Gap | Where | Solution |", "| --- | --- | --- |"])
    seen: dict[str, list[_Finding]] = {}
    for finding in findings:
        seen.setdefault(finding.solution, []).append(finding)
    for solution, grouped in seen.items():
        gap = _short(grouped[0].gap)
        if len(grouped) > 1:
            extra = len({item.gap for item in grouped}) - 1
            if extra > 0:
                gap = f"{gap} (+{extra} related)"
        where = ", ".join(dict.fromkeys(item.where for item in grouped))
        lines.append(f"| {_cell(gap)} | {_cell(where)} | {_cell(solution)} |")
    lines.append("")
    return lines


def _solution(criterion_id: str, metric: str, gap: str) -> str:
    text = f"{criterion_id} {metric} {gap}".lower()
    if "no module graph" in text:
        return "Add a module graph, or tell the skill to reject cycles, orphan modules, and high fan-out."
    if "cycle" in text or criterion_id == "deadlock":
        return "Break the cycle so each file depends in one direction."
    if criterion_id == "orphan" or "unlinked" in text:
        return "Link the unreferenced file from the entry file, or remove it from the pack."
    if criterion_id == "coupling" or "fan-out" in text:
        return "Cite one index instead of many files from the same place."
    fixes = {
        "coherence": "Keep one procedure and one vocabulary, and cite the output template from the draft step.",
        "completeness": "Add the missing contract fields and one eval scenario that walks the skill.",
        "actionability": "Add the announce line, the subskill list, an example, the output path, and an approval question.",
        "governance": "State that silence is not approval, record one risk tier, and name the review date.",
        "fluency": "Shorten the skill file and use a plain skill-card title with no BOM.",
        "job_relevance": "State the job and the hand-off to the next skill.",
        "feasibility": "Name the constraints, a failure mode, rollback, and capacity.",
        "security": "Name the threat, authentication, authorization, and how secrets are handled.",
        "scalability": "Name the scale target, a latency or throughput target, and an SLO.",
        "tech_stack": "Name the runtime and datastore and tie each one to a constraint.",
        "security_boundaries": "Name the trust boundary, the external systems, and the data classification.",
        "business_alignment": "Tie the text to the business outcome and the approval gate.",
        "constraint": "Write the rule as must or do not, with the boundary in one sentence.",
        "trace": "Name the source file that implements this rule.",
        "alignment": "Name the business or security rule this text protects.",
        "consistency": "Say this file is the source of truth and that a second rule must not be invented.",
        "trigger": "List the changes that should start this skill.",
        "procedure": "Number at least three steps the agent can follow in order.",
        "checklist": "Add a checklist of what the agent must report.",
        "boundary": "Name the behavior the skill must not allow.",
        "evaluation": "Point the skill at its eval file.",
        "stack": "Name the runtime and the UI stack.",
        "placement": "Say which directory new files belong in.",
        "api": "Name the API path shape.",
        "boundaries": "Name one change that needs an architecture decision before it is added.",
    }
    return fixes.get(criterion_id, f"Close the {metric} gap before the next review.")


def _schema_solution(statement: str, detail: str) -> str:
    text = f"{statement} {detail}".lower()
    if "secret" in text:
        return "Remove the secret and read it from the environment."
    if "card" in text or "bom" in text or "dash" in text:
        return "Rewrite the skill-card title with a real em dash and no byte-order mark."
    if "evidence" in text or "done when" in text:
        return "Add evidence to Done when and name the file that proves the skill finished."
    if "procedure" in text or "workflow" in text:
        return "Delete the extra procedure so one workflow remains."
    if "stop" in text or "final" in text or "approv" in text:
        return "Make the stop conditions block an unapproved final."
    if "template" in text:
        return "Cite the output template by filename from the draft step."
    if "heading" in text or "title" in text:
        return "Add the missing heading and put content under it."
    if "use when" in text:
        return 'Add "Use when" to the skill description.'
    if "frontmatter" in text or "description" in text or "name matches" in text:
        return "Set frontmatter name to the folder name and add a description."
    return f"Fix the failed check: {statement.rstrip('.')}."


def _short(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= 180:
        return compact
    return compact[:177] + "..."


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")


def _default_prd() -> Path:
    if _CURSOR_PRD.is_file():
        return _CURSOR_PRD
    return _ROOT / "tests" / "fixtures" / "good_prd" / "SKILL.md"


def _cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    seen: set[str] = set()
    stack: list[str] = []
    stacked: set[str] = set()
    found: list[list[str]] = []

    def visit(node: str) -> None:
        seen.add(node)
        stack.append(node)
        stacked.add(node)
        for target in graph.get(node, ()):
            if target not in seen:
                visit(target)
            elif target in stacked:
                found.append(stack[stack.index(target):] + [target])
        stack.pop()
        stacked.remove(node)

    for node in graph:
        if node not in seen:
            visit(node)
    return found


def _normalize(path: str) -> str:
    parts: list[str] = []
    for part in Path(path).as_posix().split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)
