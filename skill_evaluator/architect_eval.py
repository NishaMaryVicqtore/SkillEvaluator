"""Score an architecture skill, and an optional design, with three algorithms.

1. Schema parser: required fields, Markdown syntax, and API formatting.
2. G-Eval: feasibility, security, scalability, tech-stack viability,
   security boundaries, and business alignment. The score is the form
   integer from those steps. A separate judge model is not called.
3. Topological graph validation: dependency cycles (deadlocks), orphan
   modules, and coupling density.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from skill_evaluator.geval import CriterionScore
from skill_evaluator.parse import ParsedDocument, ParsedSkill, parse_document
from skill_evaluator.schema_checks import Assertion

GEVAL_WEIGHTS = {
    "feasibility": 0.20,
    "security": 0.15,
    "scalability": 0.15,
    "tech_stack": 0.15,
    "security_boundaries": 0.20,
    "business_alignment": 0.15,
}

STRUCTURE_WEIGHTS = {
    "deadlock": 1 / 3,
    "orphan": 1 / 3,
    "coupling": 1 / 3,
}

_SKIP_NODES = {"flowchart", "graph", "subgraph", "end", "direction", "lr", "rl", "td", "tb"}
_STACKS = (
    "python",
    "java",
    "node",
    "postgres",
    "postgresql",
    "kafka",
    "redis",
    "kubernetes",
    "dotnet",
    "golang",
    "mysql",
    "mongodb",
    "snowflake",
)
_REQUIRED_SKILL_SECTIONS = (
    "when to use",
    "when not to use",
    "execution contract",
    "approval gate",
    "done when",
)


@dataclass(frozen=True)
class ModuleGraph:
    nodes: frozenset[str]
    edges: frozenset[tuple[str, str]]
    entries: frozenset[str]


@dataclass(frozen=True)
class AlgorithmScore:
    id: str
    label: str
    score: float
    checks: tuple[Assertion, ...]
    criteria: tuple[CriterionScore, ...]


def score_architect_skill(parsed: ParsedSkill) -> tuple[AlgorithmScore, ...]:
    return (
        _schema_skill(parsed),
        _geval(parsed.pack_text, subject="skill"),
        _structure(parsed.pack_text, require_graph=False),
    )


def score_architect_design(path) -> tuple[AlgorithmScore, ...]:
    document = parse_document(path)
    return score_design_text(document)


def score_design_text(document: ParsedDocument) -> tuple[AlgorithmScore, ...]:
    return (
        _schema_design(document),
        _geval(document.text, subject="design"),
        _structure(document.text, require_graph=True),
    )


def _schema_skill(parsed: ParsedSkill) -> AlgorithmScore:
    checks = [
        _name(parsed),
        _description(parsed),
        _invocation(parsed),
        _sections(parsed),
        _markdown(parsed.pack_text),
        _api(parsed.pack_text, "openapi", r"openapi"),
        _api(parsed.pack_text, "operation_id", r"operation\s*id"),
        _api(parsed.pack_text, "json_example", r"json example|```json"),
        _api(parsed.pack_text, "security_scheme", r"security scheme"),
        _api(parsed.pack_text, "error_model", r"error model"),
        _api(parsed.pack_text, "http_path", r"\b(GET|POST|PUT|PATCH|DELETE)\s+/"),
    ]
    return _schema_score(checks)


def _schema_design(document: ParsedDocument) -> AlgorithmScore:
    titles = " ".join(document.sections)
    checks = []
    for label, needles in (
        ("Objectives", ("objective",)),
        ("Scope", ("scope",)),
        ("Components", ("component", "module")),
        ("Integrations", ("integration",)),
        ("Data design", ("data",)),
        ("Security", ("security",)),
        ("Non-functional requirements", ("non-functional", "nfr")),
        ("Risks", ("risk",)),
        ("API", ("api",)),
    ):
        passed = any(needle in titles for needle in needles)
        detail = f"{label} is present." if passed else f"The design has no {label} section."
        slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
        checks.append(Assertion(f"design_{slug}", "schema", f"Design includes {label}", passed, detail))
    checks.append(_markdown(document.text))
    checks.extend(
        [
            _api(document.text, "openapi", r"openapi"),
            _api(document.text, "operation_id", r"operation\s*id"),
            _api(document.text, "json_example", r"json example|```json"),
            _api(document.text, "security_scheme", r"security scheme"),
            _api(document.text, "error_model", r"error model"),
            _api(document.text, "http_path", r"\b(GET|POST|PUT|PATCH|DELETE)\s+/"),
        ]
    )
    return _schema_score(checks)


def _schema_score(checks: list[Assertion]) -> AlgorithmScore:
    passed = sum(1 for item in checks if item.passed)
    score = (passed / len(checks)) * 5 if checks else 0.0
    return AlgorithmScore("schema", "Schema parser", score, tuple(checks), ())


def _name(parsed: ParsedSkill) -> Assertion:
    passed = bool(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", parsed.name)) and len(parsed.name) <= 64
    return Assertion("name_kebab", "schema", "name is kebab-case and at most 64 characters", passed, f"name is {parsed.name!r}.")


def _description(parsed: ParsedSkill) -> Assertion:
    text = parsed.description
    reasons = []
    if not 40 <= len(text) <= 1024:
        reasons.append(f"length {len(text)} is outside 40–1024")
    if "Use when" not in text:
        reasons.append('description does not contain "Use when"')
    first = text.split(None, 1)[0].lower() if text else ""
    if first in {"you", "your", "i", "we", "our"}:
        reasons.append("description starts in the first or second person")
    passed = not reasons
    detail = "Description states the job and when to use it." if passed else "; ".join(reasons)
    return Assertion("description_shape", "schema", "description states what the skill does and when to use it", passed, detail)


def _invocation(parsed: ParsedSkill) -> Assertion:
    passed = parsed.disable_model_invocation
    detail = "disable-model-invocation is true." if passed else "disable-model-invocation is not true."
    return Assertion("disable_model_invocation", "schema", "disable-model-invocation is true", passed, detail)


def _sections(parsed: ParsedSkill) -> Assertion:
    missing = [title for title in _REQUIRED_SKILL_SECTIONS if not parsed.has_h2_prefix(title)]
    passed = not missing
    detail = "Required sections are present." if passed else "Missing: " + ", ".join(missing)
    return Assertion("required_sections", "schema", "Required skill sections are present", passed, detail)


def _markdown(text: str) -> Assertion:
    issues: list[str] = []
    if text.count("```") % 2 != 0:
        issues.append("a code fence is not closed")
    for number, line in enumerate(text.splitlines(), start=1):
        if re.match(r"^#{1,6}[^ #\n]", line) or re.match(r"^#{1,6}\s*$", line):
            issues.append(f"line {number} has a broken heading")
    issues.extend(_table_issues(text))
    passed = not issues
    detail = "Markdown headings, fences, and tables parse." if passed else "; ".join(issues)
    return Assertion("markdown_syntax", "schema", "Markdown syntax is valid", passed, detail)


def _table_issues(text: str) -> list[str]:
    issues: list[str] = []
    block: list[tuple[int, list[str]]] = []

    def flush() -> None:
        if len(block) < 2:
            block.clear()
            return
        width = len(block[0][1])
        for number, cells in block:
            if len(cells) != width:
                issues.append(f"line {number} table has {len(cells)} columns, header has {width}")
        block.clear()

    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip().startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            block.append((number, cells))
        else:
            flush()
    flush()
    return issues


def _api(text: str, check_id: str, pattern: str) -> Assertion:
    passed = re.search(pattern, text, re.IGNORECASE) is not None
    statement = {
        "openapi": "API section names OpenAPI",
        "operation_id": "API section names operationId",
        "json_example": "API section includes a JSON example",
        "security_scheme": "API section names a security scheme",
        "error_model": "API section names an error model",
        "http_path": "API section shows an HTTP method and path",
    }[check_id]
    detail = "Present." if passed else "Not found."
    return Assertion(f"api_{check_id}", "schema", statement, passed, detail)


def _geval(text: str, subject: str) -> AlgorithmScore:
    groups = {
        "feasibility": (
            "Feasibility",
            "The design can be built within the stated constraints, failures, rollback, and capacity.",
            (("constraint", r"constraint"), ("failure mode", r"failure"), ("rollback", r"rollback"), ("capacity", r"capacity")),
        ),
        "security": (
            "Security",
            "The design states threat handling, authentication, authorization, and secret handling.",
            (
                ("threat model", r"threat"),
                ("authentication", r"authn|authentication"),
                ("authorization", r"authz|authorization"),
                ("secrets", r"secret"),
            ),
        ),
        "scalability": (
            "Scalability",
            "The design sets a scale target, a latency or throughput target, and an SLO.",
            (("SLO", r"\bslo\b|scalability"), ("latency or throughput", r"latency|throughput"), ("scale", r"scale|capacity")),
        ),
        "tech_stack": (
            "Tech-stack viability",
            "The runtime and datastore are named and tied to a constraint.",
            _stack_signals(subject),
        ),
        "security_boundaries": (
            "Security boundaries",
            "Trust boundaries, external systems, and data classification or residency are explicit.",
            (
                ("trust boundary", r"trust boundary|boundary"),
                ("external system", r"external"),
                ("classification or residency", r"classification|residency"),
            ),
        ),
        "business_alignment": (
            "Business alignment",
            "Objectives and scope trace to the approved BRD or PRD.",
            (("objective", r"objective"), ("scope", r"scope"), ("BRD or PRD", r"\bbrd\b|\bprd\b")),
        ),
    }
    criteria = []
    for criterion_id, (label, requirement, signals) in groups.items():
        evidence = []
        gaps = []
        for name, pattern in signals:
            if re.search(pattern, text, re.IGNORECASE):
                evidence.append(f"{name} is addressed.")
            else:
                gaps.append(f"{name} is not addressed.")
        criteria.append(
            CriterionScore(
                criterion_id,
                label,
                GEVAL_WEIGHTS[criterion_id],
                _band(len(gaps)),
                requirement,
                tuple(evidence),
                tuple(gaps),
            )
        )
    score = sum(item.score * item.weight for item in criteria)
    return AlgorithmScore("geval", "G-Eval", score, (), tuple(criteria))


def _stack_signals(subject: str) -> tuple[tuple[str, str], ...]:
    if subject == "design":
        joined = "|".join(_STACKS)
        return (
            ("named technology", joined),
            ("justification", r"because|chosen|viable"),
        )
    return (
        ("runtime", r"runtime|tech stack|language"),
        ("datastore", r"datastore|database"),
        ("justification", r"because|chosen|viable|fit"),
    )


def _structure(text: str, require_graph: bool) -> AlgorithmScore:
    graph = extract_graph(text)
    cycles = _cycles(graph)
    orphans = _orphans(graph)
    graph_exists = bool(graph.nodes)
    instructed = {
        "deadlock": re.search(r"deadlock|dependency cycle|circular|dependency direction", text, re.IGNORECASE) is not None,
        "orphan": re.search(r"orphan module|unused module|unreachable module", text, re.IGNORECASE) is not None,
        "coupling": re.search(r"coupling|fan-out|fan-in|dependency direction", text, re.IGNORECASE) is not None,
    }
    deadlock_score, deadlock_evidence, deadlock_gaps = _deadlock_score(graph_exists, cycles, instructed["deadlock"], require_graph)
    orphan_score, orphan_evidence, orphan_gaps = _orphan_score(graph_exists, orphans, instructed["orphan"], require_graph)
    coupling_score, coupling_evidence, coupling_gaps = _coupling_result(graph, graph_exists, instructed["coupling"], require_graph)
    criteria = (
        CriterionScore("deadlock", "Deadlocks", STRUCTURE_WEIGHTS["deadlock"], deadlock_score, "The dependency graph has no cycle.", tuple(deadlock_evidence), tuple(deadlock_gaps)),
        CriterionScore("orphan", "Orphan modules", STRUCTURE_WEIGHTS["orphan"], orphan_score, "Every module is an entry point or is used by another module.", tuple(orphan_evidence), tuple(orphan_gaps)),
        CriterionScore("coupling", "Coupling density", STRUCTURE_WEIGHTS["coupling"], coupling_score, "Modules depend on a small number of other modules.", tuple(coupling_evidence), tuple(coupling_gaps)),
    )
    score = sum(item.score for item in criteria) / len(criteria)
    return AlgorithmScore("structure", "Topological graph validation", score, (), criteria)


def _deadlock_score(graph_exists: bool, cycles: list[str], instructed: bool, require_graph: bool):
    if graph_exists and cycles:
        return 1, [], ["Dependency cycle: " + "; ".join(cycles[:3]) + "."]
    if graph_exists:
        return 5, ["The dependency graph has no cycle."], []
    if require_graph:
        return 1, [], ["No module graph was found, so deadlocks cannot be checked."]
    if instructed:
        return 4, ["The skill tells the agent to reject dependency cycles."], ["No module graph is in the pack to measure."]
    return 1, [], ["The skill does not mention deadlocks or dependency cycles."]


def _orphan_score(graph_exists: bool, orphans: list[str], instructed: bool, require_graph: bool):
    if graph_exists and not orphans:
        return 5, ["Every module is connected or marked as an entry point."], []
    if graph_exists and len(orphans) == 1:
        return 3, [], [f"Orphan module: {orphans[0]}."]
    if graph_exists:
        return 1, [], ["Orphan modules: " + ", ".join(orphans) + "."]
    if require_graph:
        return 1, [], ["No module graph was found, so orphan modules cannot be checked."]
    if instructed:
        return 4, ["The skill tells the agent to flag orphan modules."], ["No module graph is in the pack to measure."]
    return 1, [], ["The skill does not mention orphan modules."]


def _coupling_result(graph: ModuleGraph, graph_exists: bool, instructed: bool, require_graph: bool):
    if not graph_exists:
        if require_graph:
            return 1, [], ["No module graph was found, so coupling density cannot be measured."]
        if instructed:
            return 4, ["The skill tells the agent to measure coupling."], ["No module graph is in the pack to measure."]
        return 1, [], ["The skill does not mention coupling."]
    node_count = len(graph.nodes)
    edge_count = len(graph.edges)
    possible = node_count * (node_count - 1)
    density = edge_count / possible if possible else 0.0
    out_degree: dict[str, int] = Counter()
    for source, _target in graph.edges:
        out_degree[source] += 1
    hottest = max(out_degree.values()) if out_degree else 0
    if hottest <= 2 and density <= 0.35:
        score = 5
    elif hottest <= 3 and density <= 0.4:
        score = 4
    elif density <= 0.55:
        score = 3
    elif density <= 0.75:
        score = 2
    else:
        score = 1
    evidence = [f"Coupling density is {density:.2f} across {node_count} modules. The busiest module depends on {hottest}."]
    gaps = [] if score >= 4 else ["Coupling density is high for the number of modules."]
    return score, evidence, gaps


def extract_graph(text: str) -> ModuleGraph:
    nodes: set[str] = set()
    edges: set[tuple[str, str]] = set()
    entries: set[str] = set()
    in_modules = False
    for line in text.splitlines():
        heading = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading:
            in_modules = "module" in heading.group(1).lower()
            continue
        if in_modules:
            bullet = re.match(r"^\s*[-*]\s+([A-Za-z][\w-]*)(.*)$", line)
            if bullet:
                name = bullet.group(1).lower()
                nodes.add(name)
                if "entry" in bullet.group(2).lower():
                    entries.add(name)
        _edges_from_arrows(line, nodes, edges)
    _edges_from_tables(text, nodes, edges)
    return ModuleGraph(frozenset(nodes), frozenset(edges), frozenset(entries))


def _edges_from_arrows(line: str, nodes: set[str], edges: set[tuple[str, str]]) -> None:
    if "->" not in line and "-->" not in line:
        return
    parts = re.split(r"\s*-+>\s*", line)
    tokens = []
    for part in parts:
        match = re.fullmatch(r"\s*([A-Za-z][\w-]*)\s*", part)
        if not match:
            return
        token = match.group(1).lower()
        if token in _SKIP_NODES:
            return
        tokens.append(token)
    if len(tokens) < 2:
        return
    nodes.update(tokens)
    edges.update(zip(tokens, tokens[1:]))


def _edges_from_tables(text: str, nodes: set[str], edges: set[tuple[str, str]]) -> None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        cells = _cells(line)
        if not cells:
            continue
        lowered = [cell.lower() for cell in cells]
        if not any("module" in cell or "component" in cell for cell in lowered):
            continue
        if not any("depend" in cell for cell in lowered):
            continue
        module_at = next(pos for pos, cell in enumerate(lowered) if "module" in cell or "component" in cell)
        depends_at = next(pos for pos, cell in enumerate(lowered) if "depend" in cell)
        for follower in lines[index + 1 :]:
            row = _cells(follower)
            if row is None:
                break
            if not row or all(re.fullmatch(r":?-{3,}:?", cell) for cell in row):
                continue
            if max(module_at, depends_at) >= len(row):
                continue
            source = _token(row[module_at])
            if source is None:
                continue
            nodes.add(source)
            for target in re.split(r"[,/]| and ", row[depends_at]):
                dest = _token(target)
                if dest is None or dest == source:
                    continue
                nodes.add(dest)
                edges.add((source, dest))
        return


def _cells(line: str) -> list[str] | None:
    if not line.strip().startswith("|"):
        return None
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _token(value: str) -> str | None:
    match = re.fullmatch(r"([A-Za-z][\w-]*)", value.strip())
    if not match:
        return None
    token = match.group(1).lower()
    if token in _SKIP_NODES:
        return None
    return token


def _cycles(graph: ModuleGraph) -> list[str]:
    if any(source == target for source, target in graph.edges):
        return [f"{source} -> {source}" for source, target in graph.edges if source == target]
    adjacent: dict[str, list[str]] = {node: [] for node in graph.nodes}
    for source, target in graph.edges:
        adjacent.setdefault(source, []).append(target)
        adjacent.setdefault(target, [])
    found: list[str] = []
    color = {node: 0 for node in adjacent}

    def walk(node: str, stack: list[str]) -> None:
        color[node] = 1
        stack.append(node)
        for nxt in adjacent[node]:
            if color.get(nxt, 0) == 1:
                loop = stack[stack.index(nxt) :] + [nxt]
                found.append(" -> ".join(loop))
            elif color.get(nxt, 0) == 0:
                walk(nxt, stack)
        stack.pop()
        color[node] = 2

    for node in list(adjacent):
        if color[node] == 0:
            walk(node, [])
    return found


def _orphans(graph: ModuleGraph) -> list[str]:
    incoming: Counter[str] = Counter()
    outgoing: Counter[str] = Counter()
    for source, target in graph.edges:
        outgoing[source] += 1
        incoming[target] += 1
    return sorted(
        node
        for node in graph.nodes
        if node not in graph.entries and incoming[node] == 0 and outgoing[node] == 0
    )


def _band(missing: int) -> int:
    if missing <= 0:
        return 5
    if missing == 1:
        return 4
    if missing == 2:
        return 3
    if missing == 3:
        return 2
    return 1
