"""Score governance assets with the three architecture algorithms.

1. JSON/Markdown schema parsing. Headings and eval documents become one JSON
   instance. JSON Schema draft 2020-12 checks that instance.
2. G-Eval. Criteria and steps are fixed first. The score is an integer from
   1 to 5. A separate judge model is not called.
3. Topological graph validation. Citations between the assets are a graph.
   A cycle is a deadlock, an unconnected asset is an orphan, and a high
   fan-out raises the coupling score.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from skill_evaluator.architect_eval import AlgorithmScore
from skill_evaluator.geval import CriterionScore
from skill_evaluator.parse import contains_secret
from skill_evaluator.schema_checks import Assertion, validation_errors

SCHEMA_LABEL = "JSON/Markdown Schema Parsing"
GEVAL_LABEL = "G-Eval Framework (LLM-as-a-Judge)"
GRAPH_LABEL = "Topological Graph Validation"
ARCHITECTURE_NAMES = {"architectural-standards.md", "architecture-guidelines.md"}
SKILL_SECTIONS = (
    "When to use",
    "Procedure",
    "Output checklist",
    "Evaluation",
    "Do not",
)


@dataclass(frozen=True)
class GovernanceScore:
    role: str
    path: str
    algorithms: tuple[AlgorithmScore, ...]


@dataclass(frozen=True)
class _Asset:
    kind: str
    name: str
    path: Path
    text: str
    cite_keys: tuple[str, ...]


def score_governance(
    governance_path: Path,
    cursor_path: Path | None = None,
    project_path: Path | None = None,
) -> list[GovernanceScore]:
    governance = _resolve_governance(Path(governance_path))
    if not governance.is_dir():
        raise FileNotFoundError(f"Governance directory not found: {governance}")
    cursor = _resolve_cursor(governance, cursor_path)
    project = Path(project_path).resolve() if project_path else governance.parent
    assets = _discover(governance, cursor)
    graph = _graph(assets)
    return [_score_asset(asset, graph, governance, project) for asset in assets]


def _resolve_governance(path: Path) -> Path:
    if (path / ".ai-governance").is_dir():
        return (path / ".ai-governance").resolve()
    return path.resolve()


def _resolve_cursor(governance: Path, cursor_path: Path | None) -> Path | None:
    if cursor_path is not None:
        return Path(cursor_path).resolve()
    sibling = governance.parent / ".cursor"
    if sibling.is_dir():
        return sibling.resolve()
    return None


def _discover(governance: Path, cursor: Path | None) -> list[_Asset]:
    assets: list[_Asset] = []
    for path in sorted(governance.glob("*.md")):
        if "policy" in path.name.lower():
            assets.append(_markdown_asset("policy", path.stem, path, _cite_keys(governance, path)))
        elif path.name in ARCHITECTURE_NAMES:
            assets.append(_markdown_asset("architecture", path.stem, path, _cite_keys(governance, path)))
    rules = governance / "rules"
    if rules.is_dir():
        for path in sorted(rules.glob("*.md")):
            kind = "architecture" if path.name in ARCHITECTURE_NAMES else "rule"
            assets.append(_markdown_asset(kind, path.stem, path, _cite_keys(governance, path)))
    skills = governance / "skills"
    if skills.is_dir():
        for skill_dir in sorted(item for item in skills.iterdir() if item.is_dir()):
            skill_path = skill_dir / "SKILL.md"
            eval_path = skill_dir / "evals.json"
            if skill_path.is_file():
                text = _read(skill_path)
                frontmatter = _frontmatter(text) or {}
                description = str(frontmatter.get("description") or "")
                kind = "architecture" if "architect" in skill_dir.name.lower() or "architect" in description.lower() else "skill"
                assets.append(_markdown_asset(kind, skill_dir.name, skill_path, (skill_dir.name, f"skills/{skill_dir.name}")))
            if eval_path.is_file():
                assets.append(
                    _Asset(
                        "eval",
                        skill_dir.name,
                        eval_path,
                        _read(eval_path),
                        (f"skills/{skill_dir.name}/evals.json",),
                    )
                )
    promptfoo = governance / "ci" / "promptfoo.yaml"
    if promptfoo.is_file():
        assets.append(_markdown_asset("eval", "promptfoo", promptfoo, ("ci/promptfoo.yaml",)))
    if cursor is not None and cursor.is_dir():
        rules_dir = cursor / "rules" if (cursor / "rules").is_dir() else cursor
        for path in sorted(rules_dir.glob("*.mdc")):
            assets.append(_markdown_asset("rule", path.stem, path, (f".cursor/rules/{path.name}", path.name)))
    return assets


def _markdown_asset(kind: str, name: str, path: Path, cite_keys: tuple[str, ...]) -> _Asset:
    return _Asset(kind, name, path, _read(path), cite_keys)


def _cite_keys(governance: Path, path: Path) -> tuple[str, ...]:
    relative = path.resolve().relative_to(governance.parent).as_posix()
    short = relative.split(".ai-governance/", 1)[-1]
    keys = [relative]
    if short != relative:
        keys.append(short)
    return tuple(keys)


def _graph(assets: list[_Asset]) -> dict[str, set[str]]:
    edges: dict[str, set[str]] = {asset.path.as_posix(): set() for asset in assets}
    for source in assets:
        for target in assets:
            if source.path == target.path:
                continue
            if any(key and key in source.text for key in target.cite_keys):
                edges[source.path.as_posix()].add(target.path.as_posix())
    return edges


def _score_asset(asset: _Asset, graph: dict[str, set[str]], governance: Path, project: Path) -> GovernanceScore:
    schema = _schema(asset, governance, project)
    geval = _geval(asset)
    structure = _structure(asset, graph)
    role = {
        "policy": "Policy",
        "rule": "Rule",
        "skill": "Skill",
        "eval": "Eval",
        "architecture": "Architecture skill",
    }[asset.kind]
    return GovernanceScore(f"{role} — {asset.name}", str(asset.path), (schema, geval, structure))


def _schema(asset: _Asset, governance: Path, project: Path) -> AlgorithmScore:
    if asset.kind == "eval" and asset.path.suffix == ".json":
        checks = _eval_json_checks(asset, governance, project)
    elif asset.kind == "eval":
        checks = _promptfoo_checks(asset)
    elif asset.kind == "policy":
        checks = _prose_checks(asset, ("secret", "credential"), ("authenticat", "token"), ("do not", "never", "must not"))
    elif asset.kind == "architecture":
        checks = _prose_checks(asset, ("node", "express"), ("file placement", "frontend/src", "backend/"), ("/api/", "rest"), ("do not", "patterns to avoid"))
    elif asset.kind == "skill":
        checks = _skill_checks(asset)
    else:
        checks = _rule_checks(asset)
    checks.append(_no_secret(asset))
    _ = validation_errors(checks)
    passed = sum(1 for item in checks if item.passed)
    score = (passed / len(checks)) * 5 if checks else 0.0
    return AlgorithmScore("schema", SCHEMA_LABEL, score, tuple(checks), ())


def _prose_checks(asset: _Asset, *groups: tuple[str, ...]) -> list[Assertion]:
    labels = {
        "policy": ("Policy covers secrets or credentials", "Policy covers authentication or tokens", "Policy states a prohibition"),
        "architecture": ("Architecture skill names the stack", "Architecture skill places files", "Architecture skill names an API shape", "Architecture skill names a pattern to avoid"),
    }
    names = labels.get(asset.kind, tuple(f"Check {index}" for index in range(len(groups))))
    checks = [_heading(asset)]
    for index, needles in enumerate(groups):
        found = _has(asset.text, *needles)
        checks.append(
            Assertion(
                f"group_{index}",
                "schema",
                names[index] if index < len(names) else f"Required language {index + 1}",
                found,
                "Present." if found else "Missing: " + ", ".join(needles),
            )
        )
    return checks


def _rule_checks(asset: _Asset) -> list[Assertion]:
    checks = [
        _heading(asset),
        _flag(asset, "constraint", "Rule states a constraint", ("must", "do not", "never", "forbidden")),
    ]
    frontmatter = _frontmatter(asset.text)
    if asset.path.suffix == ".mdc":
        checks.append(Assertion("frontmatter", "schema", "Cursor rule has frontmatter", frontmatter is not None, "Present." if frontmatter else "Missing."))
        description = bool(frontmatter and frontmatter.get("description"))
        checks.append(Assertion("description", "schema", "Cursor rule has a description", description, "Present." if description else "Missing."))
        scoped = bool(frontmatter and ("alwaysApply" in frontmatter or "globs" in frontmatter))
        checks.append(Assertion("scope", "schema", "Cursor rule sets alwaysApply or globs", scoped, "Present." if scoped else "Missing."))
        cited = ".ai-governance" in asset.text
        checks.append(Assertion("source", "schema", "Cursor rule points at .ai-governance", cited, "Present." if cited else "Missing."))
    if "booking" in asset.name.lower():
        checks.append(_flag(asset, "booking_source", "Booking rule names the cutoff source", ("cutoff", "8:00", "rules.js")))
    if "auth" in asset.name.lower() or "trimble-id" in asset.name.lower():
        passed = _has(asset.text, "trimble id") and "localstorage" in asset.text.lower()
        checks.append(Assertion("auth_rule", "schema", "Auth rule requires Trimble ID and forbids localStorage", passed, "Present." if passed else "Missing Trimble ID or localStorage."))
    return checks


def _skill_checks(asset: _Asset) -> list[Assertion]:
    frontmatter = _frontmatter(asset.text)
    description = str((frontmatter or {}).get("description") or "").strip()
    name_ok = bool(frontmatter and str(frontmatter.get("name")) == asset.name)
    checks = [
        Assertion("frontmatter", "schema", "SKILL.md has frontmatter", frontmatter is not None, "Present." if frontmatter else "Missing."),
        Assertion("name", "schema", "Frontmatter name matches the folder", name_ok, f"name is {None if not frontmatter else frontmatter.get('name')!r}."),
        Assertion("description", "schema", "Frontmatter has a description", bool(description), "Present." if description else "Missing."),
    ]
    for section in SKILL_SECTIONS:
        present = f"## {section}" in asset.text
        checks.append(Assertion(_slug(section), "schema", f"SKILL.md has {section}", present, "Present." if present else "Missing."))
    steps = _numbered_steps(asset.text)
    checks.append(Assertion("procedure_steps", "schema", "Procedure has at least three numbered steps", steps >= 3, f"{steps} numbered steps."))
    return checks


def _eval_json_checks(asset: _Asset, governance: Path, project: Path) -> list[Assertion]:
    try:
        payload = json.loads(asset.text)
    except json.JSONDecodeError as exc:
        return [Assertion("json", "schema", "evals.json parses", False, str(exc))]
    schema_ok, schema_detail = _validate_eval_schema(payload)
    checks = [
        Assertion("json", "schema", "evals.json parses", True, "Parsed."),
        Assertion("eval_schema", "schema", "evals.json matches the eval schema", schema_ok, schema_detail),
        Assertion("skill_name", "schema", "evals.json names this skill", isinstance(payload, dict) and payload.get("skill") == asset.name, f"skill is {None if not isinstance(payload, dict) else payload.get('skill')!r}."),
    ]
    if isinstance(payload, dict) and isinstance(payload.get("assets"), list):
        for index, item in enumerate(payload["assets"], start=1):
            checks.extend(_asset_needles(index, item, governance, project))
    return checks


def _promptfoo_checks(asset: _Asset) -> list[Assertion]:
    try:
        payload = yaml.safe_load(asset.text)
    except yaml.YAMLError as exc:
        return [Assertion("yaml", "schema", "promptfoo.yaml parses", False, str(exc))]
    prompts = payload.get("prompts") if isinstance(payload, dict) else None
    tests = payload.get("tests") if isinstance(payload, dict) else None
    asserts = isinstance(tests, list) and all(isinstance(item, dict) and item.get("assert") for item in tests)
    return [
        Assertion("yaml", "schema", "promptfoo.yaml parses", isinstance(payload, dict), "Parsed." if isinstance(payload, dict) else "Not a mapping."),
        Assertion("prompts", "schema", "promptfoo.yaml lists prompts", isinstance(prompts, list) and len(prompts) > 0, f"{0 if not isinstance(prompts, list) else len(prompts)} prompts."),
        Assertion("tests", "schema", "promptfoo.yaml lists tests with assertions", asserts, "Each test has an assert list." if asserts else "A test is missing assert."),
    ]


def _validate_eval_schema(payload: object) -> tuple[bool, str]:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["skill", "tests"],
        "properties": {
            "skill": {"type": "string", "minLength": 1},
            "tests": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["file", "name"],
                    "properties": {
                        "file": {"type": "string", "minLength": 1},
                        "name": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    }
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    if not errors:
        return True, "Draft 2020-12 accepted the eval document."
    return False, errors[0].message


def _asset_needles(index: int, item: object, governance: Path, project: Path) -> list[Assertion]:
    if not isinstance(item, dict):
        return [Assertion(f"asset_{index}", "schema", f"Asset {index} is an object", False, "Not an object.")]
    relative = str(item.get("file") or "")
    target = _resolve_cited(relative, governance, project)
    if target is None or not target.is_file():
        if relative.startswith(".ai-governance/"):
            return [Assertion(f"asset_{index}", "schema", f"Asset {index} file exists", False, relative)]
        return []
    text = _read(target)
    missing = [needle for needle in item.get("contains") or [] if needle not in text]
    forbidden = [needle for needle in item.get("notContains") or [] if needle.lower() in text.lower()]
    problems = [f"missing {needle!r}" for needle in missing] + [f"must not contain {needle!r}" for needle in forbidden]
    return [
        Assertion(
            f"asset_{index}",
            "schema",
            f"Asset {index} matches {relative}",
            not problems,
            "Matched." if not problems else "; ".join(problems),
        )
    ]


def _resolve_cited(relative: str, governance: Path, project: Path) -> Path | None:
    normalized = relative.replace("\\", "/").lstrip("/")
    if not normalized:
        return None
    if normalized.startswith(".ai-governance/"):
        return governance.parent / normalized
    if project.is_dir():
        return project / normalized
    return None


def _geval(asset: _Asset) -> AlgorithmScore:
    if asset.kind == "policy":
        criteria = (
            _signals("secrets", "Secrets", 0.25, "The policy forbids hardcoded secrets and committed env files.", asset.text, ("secret", ".env", "credential")),
            _signals("authentication", "Authentication", 0.25, "The policy covers tokens and authentication.", asset.text, ("token", "authenticat", "localstorage")),
            _signals("prohibition", "Prohibition", 0.25, "The policy states what an agent must not do.", asset.text, ("do not", "never", "must not")),
            _signals("example", "Failure example", 0.25, "The policy shows a rejected outcome.", asset.text, ("example", "rejected", "ungoverned")),
        )
    elif asset.kind == "architecture":
        criteria = (
            _signals("stack", "Tech-stack viability", 0.25, "The architecture names the runtime and the UI stack.", asset.text, ("node", "express", "react")),
            _signals("placement", "File placement", 0.25, "The architecture says where new files go.", asset.text, ("file placement", "frontend", "backend")),
            _signals("api", "API shape", 0.25, "The architecture names the API shape.", asset.text, ("/api/", "json", "rest")),
            _signals("boundaries", "Patterns to avoid", 0.25, "The architecture names a change that needs approval.", asset.text, ("do not", "without", "database")),
        )
    elif asset.kind == "skill":
        criteria = (
            _signals("trigger", "When to use", 0.20, "The skill says which changes should trigger it.", asset.text, ("when to use", "adding", "modifying")),
            _procedure(asset.text),
            _signals("checklist", "Output checklist", 0.20, "The skill lists what the agent must report.", asset.text, ("output checklist", "- [ ]", "report")),
            _signals("boundary", "Do not", 0.20, "The skill names behavior it must not allow.", asset.text, ("do not", "must not", "still refuse")),
            _signals("evaluation", "Evaluation", 0.20, "The skill points at its eval file.", asset.text, ("evaluation", "evals.json", "skills:eval")),
        )
    elif asset.kind == "eval":
        criteria = _eval_criteria(asset)
    else:
        criteria = (
            _signals("constraint", "Constraint", 0.25, "The rule states a constraint an agent can follow.", asset.text, ("must", "do not", "never", "forbidden")),
            _signals("trace", "Implementation trace", 0.25, "The rule names the code or document that carries it.", asset.text, ("rules.js", "backend", ".ai-governance", "oauth")),
            _signals("alignment", "Business alignment", 0.25, "The rule names the business or security rule it protects.", asset.text, _alignment_needles(asset)),
            _signals("consistency", "Single source", 0.25, "The rule tells the agent not to invent a second rule.", asset.text, ("match", "source of truth", "do not", "must not")),
        )
    score = sum(item.score * item.weight for item in criteria)
    return AlgorithmScore("geval", GEVAL_LABEL, score, (), criteria)


def _eval_criteria(asset: _Asset) -> tuple[CriterionScore, ...]:
    if asset.path.suffix == ".json":
        try:
            payload = json.loads(asset.text)
        except json.JSONDecodeError:
            payload = {}
        tests = payload.get("tests") if isinstance(payload, dict) else []
        assets = payload.get("assets") if isinstance(payload, dict) else []
        test_count = len(tests) if isinstance(tests, list) else 0
        named = isinstance(payload, dict) and payload.get("skill") == asset.name
        linked = isinstance(assets, list) and bool(assets) and all(_asset_linked(item) for item in assets)
        return (
            _count_score("coverage", "Case coverage", 0.25, "The eval lists the cases the skill owns.", test_count, "test cases"),
            CriterionScore("traceability", "Traceability", 0.25, 5 if named else 1, "The eval names its skill.", (("The skill field matches the folder.",) if named else ()), (() if named else ("The skill field does not match the folder.",))),
            CriterionScore("assets", "Asset linkage", 0.25, 5 if linked else 2, "Each asset names a file and the text it must contain.", (("Assets name a file and required text.",) if linked else ()), (() if linked else ("An asset is missing a file or contains list.",))),
            _signals("safety", "Safety", 0.25, "The eval does not embed a secret or an injection phrase.", asset.text, ("test", "file", "name")),
        )
    return (
        _signals("prompts", "Prompt coverage", 0.34, "The promptfoo file gives the judge a prompt.", asset.text, ("prompts:", "you are")),
        _signals("assertions", "Assertions", 0.33, "Each case has an assertion.", asset.text, ("assert:", "llm-rubric")),
        _signals("policy", "Policy trace", 0.33, "The prompts cite the governance files they must follow.", asset.text, (".ai-governance", "rules/")),
    )


def _alignment_needles(asset: _Asset) -> tuple[str, ...]:
    name = asset.name.lower()
    if "booking" in name:
        return ("booking", "cutoff", "rules.js")
    if "auth" in name or "trimble-id" in name:
        return ("trimble id", "oauth", "localstorage")
    if asset.path.suffix == ".mdc":
        return ("security", "architecture", "booking")
    return ("must", "policy")


def _asset_linked(item: object) -> bool:
    return isinstance(item, dict) and bool(item.get("file")) and bool(item.get("contains") or item.get("notContains"))


def _procedure(text: str) -> CriterionScore:
    steps = _numbered_steps(text)
    if steps >= 5:
        score = 5
    elif steps >= 3:
        score = 4
    elif steps >= 1:
        score = 3
    else:
        score = 1
    evidence = (f"The procedure has {steps} numbered steps.",) if steps else ()
    gaps = () if steps >= 3 else ("The procedure has fewer than three numbered steps.",)
    return CriterionScore("procedure", "Procedure", 0.20, score, "The procedure is a numbered sequence the agent can follow.", evidence, gaps)


def _structure(asset: _Asset, graph: dict[str, set[str]]) -> AlgorithmScore:
    node = asset.path.as_posix()
    cycles = _cycles(graph)
    on_cycle = any(node in cycle for cycle in cycles)
    outgoing = graph.get(node, set())
    incoming = {source for source, targets in graph.items() if node in targets}
    if on_cycle:
        deadlock_score, deadlock_gaps = 1, ("This asset is on a citation cycle: " + " -> ".join(_names(next(cycle for cycle in cycles if node in cycle))) + ".",)
        deadlock_evidence: tuple[str, ...] = ()
    else:
        deadlock_score, deadlock_evidence, deadlock_gaps = 5, ("This asset is not on a citation cycle.",), ()
    if not incoming and not outgoing:
        orphan_score, orphan_evidence, orphan_gaps = 1, (), ("Nothing cites this asset, and it cites nothing in the bundle.",)
    else:
        orphan_score, orphan_evidence, orphan_gaps = 5, (f"Citations in: {len(incoming)}. Citations out: {len(outgoing)}.",), ()
    fan_out = len(outgoing)
    if fan_out <= 4:
        coupling_score, coupling_gaps = 5, ()
    elif fan_out <= 8:
        coupling_score, coupling_gaps = 4, ()
    elif fan_out <= 12:
        coupling_score, coupling_gaps = 3, (f"This asset cites {fan_out} other assets.",)
    else:
        coupling_score, coupling_gaps = 2, (f"This asset cites {fan_out} other assets.",)
    coupling_evidence = (f"Fan-out is {fan_out}.",)
    criteria = (
        CriterionScore("deadlock", "Deadlocks", 1 / 3, deadlock_score, "Citations between assets do not form a cycle.", deadlock_evidence, deadlock_gaps),
        CriterionScore("orphan", "Orphan modules", 1 / 3, orphan_score, "Every asset is cited or cites another asset in the bundle.", orphan_evidence, orphan_gaps),
        CriterionScore("coupling", "Coupling density", 1 / 3, coupling_score, "An asset cites a small set of other assets.", coupling_evidence, coupling_gaps),
    )
    score = sum(item.score for item in criteria) / len(criteria)
    return AlgorithmScore("structure", GRAPH_LABEL, score, (), criteria)


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
                start = stack.index(target)
                found.append(stack[start:] + [target])
        stack.pop()
        stacked.remove(node)

    for node in graph:
        if node not in seen:
            visit(node)
    return found


def _names(cycle: list[str]) -> list[str]:
    return [Path(item).stem for item in cycle]


def _signals(criterion_id: str, label: str, weight: float, requirement: str, text: str, needles: tuple[str, ...]) -> CriterionScore:
    evidence = tuple(needle for needle in needles if needle.lower() in text.lower())
    gaps = tuple(f"Missing {needle}." for needle in needles if needle.lower() not in text.lower())
    missing = len(gaps)
    if missing == 0:
        score = 5
    elif missing == 1:
        score = 4
    elif missing == 2:
        score = 3
    elif missing == 3:
        score = 2
    else:
        score = 1
    return CriterionScore(criterion_id, label, weight, score, requirement, evidence, gaps)


def _count_score(criterion_id: str, label: str, weight: float, requirement: str, count: int, noun: str) -> CriterionScore:
    if count >= 8:
        score = 5
    elif count >= 4:
        score = 4
    elif count >= 1:
        score = 3
    else:
        score = 1
    evidence = (f"{count} {noun}.",) if count else ()
    gaps = () if count else (f"No {noun}.",)
    return CriterionScore(criterion_id, label, weight, score, requirement, evidence, gaps)


def _heading(asset: _Asset) -> Assertion:
    passed = bool(re.search(r"(?m)^#\s+\S", asset.text))
    return Assertion("title", "schema", f"{asset.kind} has a title", passed, "Present." if passed else "Missing a level-1 heading.")


def _flag(asset: _Asset, check_id: str, statement: str, needles: tuple[str, ...]) -> Assertion:
    passed = _has(asset.text, *needles)
    return Assertion(check_id, "schema", statement, passed, "Present." if passed else "Missing: " + ", ".join(needles))


def _no_secret(asset: _Asset) -> Assertion:
    passed = not contains_secret(asset.text)
    return Assertion("no_secret", "schema", "No secret marker is hardcoded", passed, "No secret markers found." if passed else "A secret-shaped token is present.")


def _has(text: str, *needles: str) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def _numbered_steps(text: str) -> int:
    return sum(1 for line in text.splitlines() if re.match(r"\s*\d+\.\s+\S", line))


def _frontmatter(text: str) -> dict | None:
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        loaded = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""
