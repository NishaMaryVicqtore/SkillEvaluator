"""Evaluate AGL rules, skills, policies, evals, and architecture skills."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from tse.models import GovernanceAsset, GovernanceReport
from tse.tier1_static import PROMPT_INJECTION_PATTERNS, SECRET_PATTERNS


POLICY_NAMES = {"global-security-policy.md"}
ARCHITECTURE_NAMES = {"architectural-standards.md", "architecture-guidelines.md"}
SKIP_ROOT_NAMES = {
    "readme.md",
    "adoption.md",
    "pr_review_checklist.md",
}
SKILL_SECTIONS = (
    "## When to use",
    "## Procedure",
    "## Output checklist",
    "## Evaluation",
    "## Do not",
)


def evaluate_governance(
    governance_path: Path,
    cursor_path: Path | None = None,
    project_path: Path | None = None,
) -> GovernanceReport:
    """Score the behavioral assets in an `.ai-governance` tree and Cursor rules."""
    governance = _resolve_governance(Path(governance_path))
    if not governance.is_dir():
        asset = _asset("policy", governance.name, governance, ["Governance directory does not exist."])
        return GovernanceReport(
            governance_path=str(governance),
            passed=False,
            assets=[asset],
        )

    cursor = _resolve_cursor(governance, cursor_path)
    project = Path(project_path).resolve() if project_path else None
    assets = [
        *_policies(governance),
        *_rules(governance),
        *_architecture(governance),
        *_skills(governance),
        *_evals(governance, project),
        *_cursor_rules(cursor),
    ]
    assets.extend(_missing_kinds(assets, cursor))
    return GovernanceReport(
        governance_path=str(governance),
        cursor_path=str(cursor) if cursor else None,
        project_path=str(project) if project else None,
        passed=all(item.passed for item in assets) and bool(assets),
        assets=assets,
    )


def _resolve_governance(path: Path) -> Path:
    if (path / ".ai-governance").is_dir():
        return path / ".ai-governance"
    return path


def _resolve_cursor(governance: Path, cursor_path: Path | None) -> Path | None:
    if cursor_path is not None:
        return Path(cursor_path)
    sibling = governance.parent / ".cursor"
    if sibling.is_dir():
        return sibling
    return None


def _policies(governance: Path) -> list[GovernanceAsset]:
    found = []
    for path in sorted(governance.glob("*.md")):
        if path.name.lower() in POLICY_NAMES or "policy" in path.name.lower():
            if path.name.lower() in SKIP_ROOT_NAMES:
                continue
            found.append(_policy(path))
    return found


def _rules(governance: Path) -> list[GovernanceAsset]:
    rules_dir = governance / "rules"
    if not rules_dir.is_dir():
        return []
    found = []
    for path in sorted(rules_dir.glob("*.md")):
        if path.name in ARCHITECTURE_NAMES:
            continue
        found.append(_rule(path, cursor=False))
    return found


def _architecture(governance: Path) -> list[GovernanceAsset]:
    found = []
    root_arch = governance / "architectural-standards.md"
    if root_arch.is_file():
        found.append(_architecture_doc(root_arch))
    guidelines = governance / "rules" / "architecture-guidelines.md"
    if guidelines.is_file():
        found.append(_architecture_doc(guidelines))
    skills_dir = governance / "skills"
    if skills_dir.is_dir():
        for skill_dir in sorted(item for item in skills_dir.iterdir() if item.is_dir()):
            skill_path = skill_dir / "SKILL.md"
            if skill_path.is_file() and _is_architecture_skill(skill_dir.name, skill_path):
                found.append(_skill(skill_path, kind="architecture"))
    return found


def _skills(governance: Path) -> list[GovernanceAsset]:
    skills_dir = governance / "skills"
    if not skills_dir.is_dir():
        return []
    found = []
    for skill_dir in sorted(item for item in skills_dir.iterdir() if item.is_dir()):
        skill_path = skill_dir / "SKILL.md"
        if not skill_path.is_file():
            found.append(_asset("skill", skill_dir.name, skill_dir, ["SKILL.md is missing."]))
            continue
        if _is_architecture_skill(skill_dir.name, skill_path):
            continue
        found.append(_skill(skill_path, kind="skill"))
    return found


def _evals(governance: Path, project: Path | None) -> list[GovernanceAsset]:
    found = []
    skills_dir = governance / "skills"
    if skills_dir.is_dir():
        for skill_dir in sorted(item for item in skills_dir.iterdir() if item.is_dir()):
            eval_path = skill_dir / "evals.json"
            if eval_path.is_file():
                found.append(_eval_json(eval_path, skill_dir.name, governance, project))
            else:
                found.append(_asset("eval", skill_dir.name, skill_dir, ["evals.json is missing."]))
    promptfoo = governance / "ci" / "promptfoo.yaml"
    if promptfoo.is_file():
        found.append(_promptfoo(promptfoo))
    return found


def _cursor_rules(cursor: Path | None) -> list[GovernanceAsset]:
    if cursor is None or not cursor.is_dir():
        return []
    rules_dir = cursor / "rules" if (cursor / "rules").is_dir() else cursor
    return [_rule(path, cursor=True) for path in sorted(rules_dir.glob("*.mdc"))]


def _missing_kinds(assets: list[GovernanceAsset], cursor: Path | None) -> list[GovernanceAsset]:
    present = {item.kind for item in assets}
    expected = {
        "policy": "No policy file was found. Expected a markdown file whose name contains 'policy'.",
        "rule": "No rule file was found under rules/.",
        "skill": "No skill directory with SKILL.md was found under skills/.",
        "eval": "No evals.json or ci/promptfoo.yaml was found.",
        "architecture": "No architecture skill or architecture standard was found.",
    }
    missing = []
    for kind, message in expected.items():
        if kind not in present:
            missing.append(
                GovernanceAsset(
                    kind=kind,
                    name=f"missing {kind}",
                    path="",
                    passed=False,
                    score=0.0,
                    violations=[message],
                )
            )
    if cursor is not None and not any(item.path.endswith(".mdc") for item in assets):
        missing.append(
            GovernanceAsset(
                kind="rule",
                name="cursor rules",
                path=str(cursor),
                passed=False,
                score=0.0,
                violations=["No .mdc rules were found in the Cursor rules directory."],
            )
        )
    return missing


def _policy(path: Path) -> GovernanceAsset:
    text = _read(path)
    violations = _security(text, path.name)
    violations.extend(
        _expect(
            [
                ("Policy has a title", text.lstrip().startswith("#")),
                ("Policy covers secrets or credentials", _contains(text, "secret", "credential")),
                ("Policy covers authentication or tokens", _contains(text, "authenticat", "token")),
                ("Policy forbids local secret storage", _contains(text, "localstorage", ".env")),
                ("Policy states a prohibition", _contains(text, "do not", "never", "must not")),
            ]
        )
    )
    return _asset("policy", path.stem, path, violations)


def _rule(path: Path, cursor: bool) -> GovernanceAsset:
    text = _read(path)
    violations = _security(text, path.name)
    frontmatter = _frontmatter(text)
    checks = [
        ("Rule has a title", "# " in text),
        ("Rule states a constraint", _contains(text, "must", "do not", "never", "forbidden")),
    ]
    if cursor:
        checks.extend(
            [
                ("Cursor rule has frontmatter", frontmatter is not None),
                ("Cursor rule has a description", bool(frontmatter and frontmatter.get("description"))),
                (
                    "Cursor rule sets alwaysApply or globs",
                    bool(frontmatter and ("alwaysApply" in frontmatter or "globs" in frontmatter)),
                ),
                ("Cursor rule points at .ai-governance", ".ai-governance" in text),
            ]
        )
    if "booking" in path.name.lower():
        checks.append(("Booking rule names the cutoff source", _contains(text, "cutoff", "8:00", "rules.js")))
    if "auth" in path.name.lower() or "trimble-id" in path.name.lower():
        checks.append(("Auth rule requires Trimble ID and forbids localStorage", _contains(text, "trimble id") and "localstorage" in text.lower()))
    violations.extend(_expect(checks))
    return _asset("rule", path.stem, path, violations)


def _architecture_doc(path: Path) -> GovernanceAsset:
    text = _read(path)
    violations = _security(text, path.name)
    violations.extend(
        _expect(
            [
                ("Architecture asset names the stack", _contains(text, "express", "node")),
                ("Architecture asset places files", _contains(text, "file placement", "frontend/src", "backend/")),
                ("Architecture asset names an API shape", _contains(text, "/api/", "rest")),
                ("Architecture asset names a pattern to avoid", _contains(text, "do not", "patterns to avoid")),
            ]
        )
    )
    return _asset("architecture", path.stem, path, violations)


def _skill(path: Path, kind: str) -> GovernanceAsset:
    text = _read(path)
    frontmatter = _frontmatter(text)
    name = path.parent.name
    violations = _security(text, f"{name}/SKILL.md")
    description = ""
    if isinstance(frontmatter, dict):
        description = str(frontmatter.get("description") or "").strip()
    violations.extend(
        _expect(
            [
                ("SKILL.md has frontmatter", frontmatter is not None),
                ("Frontmatter name matches the folder", bool(frontmatter and str(frontmatter.get("name")) == name)),
                ("Frontmatter has a description", bool(description)),
                *[
                    (f"SKILL.md has {section}", section in text)
                    for section in SKILL_SECTIONS
                ],
                ("Procedure has at least three numbered steps", _procedure_steps(text) >= 3),
            ]
        )
    )
    return _asset(kind, name, path, violations)


def _eval_json(
    path: Path,
    skill_name: str,
    governance: Path,
    project: Path | None,
) -> GovernanceAsset:
    violations: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return _asset("eval", skill_name, path, [f"evals.json does not parse: {exc}"])
    violations.extend(_security(json.dumps(payload), path.name))
    tests = payload.get("tests") if isinstance(payload, dict) else None
    assets = payload.get("assets") if isinstance(payload, dict) else None
    violations.extend(
        _expect(
            [
                ("evals.json is an object", isinstance(payload, dict)),
                ("evals.json names this skill", isinstance(payload, dict) and payload.get("skill") == skill_name),
                ("evals.json lists at least one test", isinstance(tests, list) and len(tests) > 0),
            ]
        )
    )
    if isinstance(tests, list):
        for index, case in enumerate(tests, start=1):
            if not isinstance(case, dict) or not str(case.get("file") or "").strip() or not str(case.get("name") or "").strip():
                violations.append(f"Test {index} needs a file and a name.")
    if assets is not None and not isinstance(assets, list):
        violations.append("assets must be a list.")
    if isinstance(assets, list):
        for index, asset in enumerate(assets, start=1):
            violations.extend(_eval_asset(index, asset, governance, project))
    return _asset("eval", skill_name, path, violations)


def _eval_asset(index: int, asset: object, governance: Path, project: Path | None) -> list[str]:
    if not isinstance(asset, dict):
        return [f"Asset {index} must be an object."]
    violations = []
    if not str(asset.get("description") or "").strip():
        violations.append(f"Asset {index} needs a description.")
    relative = str(asset.get("file") or "").strip()
    if not relative:
        violations.append(f"Asset {index} needs a file.")
        return violations
    contains = asset.get("contains")
    not_contains = asset.get("notContains")
    if contains is not None and not _string_list(contains):
        violations.append(f"Asset {index} contains must be a list of strings.")
    if not_contains is not None and not _string_list(not_contains):
        violations.append(f"Asset {index} notContains must be a list of strings.")
    target = _resolve_asset_file(relative, governance, project)
    if target is None:
        return violations
    if not target.is_file():
        violations.append(f"Asset {index} file is missing: {relative}")
        return violations
    text = target.read_text(encoding="utf-8")
    for needle in contains or []:
        if needle not in text:
            violations.append(f"Asset {index} is missing {needle!r} in {relative}.")
    for needle in not_contains or []:
        if needle.lower() in text.lower():
            violations.append(f"Asset {index} must not contain {needle!r} in {relative}.")
    return violations


def _promptfoo(path: Path) -> GovernanceAsset:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return _asset("eval", path.stem, path, [f"promptfoo.yaml does not parse: {exc}"])
    text = path.read_text(encoding="utf-8")
    violations = _security(text, path.name)
    prompts = payload.get("prompts") if isinstance(payload, dict) else None
    tests = payload.get("tests") if isinstance(payload, dict) else None
    violations.extend(
        _expect(
            [
                ("promptfoo.yaml is a mapping", isinstance(payload, dict)),
                ("promptfoo.yaml lists prompts", isinstance(prompts, list) and len(prompts) > 0),
                ("promptfoo.yaml lists tests", isinstance(tests, list) and len(tests) > 0),
            ]
        )
    )
    if isinstance(tests, list):
        for index, case in enumerate(tests, start=1):
            if not isinstance(case, dict) or not case.get("assert"):
                violations.append(f"Promptfoo test {index} needs an assert list.")
    return _asset("eval", "promptfoo", path, violations)


def _is_architecture_skill(folder_name: str, skill_path: Path) -> bool:
    frontmatter = _frontmatter(_read(skill_path)) or {}
    description = str(frontmatter.get("description") or "").lower()
    return "architect" in folder_name.lower() or "architect" in description


def _resolve_asset_file(relative: str, governance: Path, project: Path | None) -> Path | None:
    normalized = relative.replace("\\", "/").lstrip("/")
    if normalized.startswith(".ai-governance/"):
        return governance.parent / normalized
    if project is None:
        return None
    return project / normalized


def _procedure_steps(text: str) -> int:
    body = _section(text, "## Procedure")
    return sum(1 for line in body.splitlines() if line.strip()[:2].rstrip(".").isdigit() or _numbered(line))


def _numbered(line: str) -> bool:
    stripped = line.strip()
    digits = ""
    for char in stripped:
        if char.isdigit():
            digits += char
        else:
            break
    return bool(digits) and stripped[len(digits):].startswith(".")


def _section(text: str, heading: str) -> str:
    start = text.find(heading)
    if start < 0:
        return ""
    rest = text[start + len(heading):]
    next_heading = rest.find("\n## ")
    if next_heading < 0:
        return rest
    return rest[:next_heading]


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


def _security(text: str, label: str) -> list[str]:
    violations = []
    for secret_name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            violations.append(f"Hardcoded {secret_name} detected in {label}")
    for phrase, pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(text):
            violations.append(f"Prompt injection phrase '{phrase}' detected in {label}")
    return violations


def _contains(text: str, *needles: str) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def _string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def _expect(checks: list[tuple[str, bool]]) -> list[str]:
    return [statement for statement, passed in checks if not passed]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def _asset(kind: str, name: str, path: Path, violations: list[str]) -> GovernanceAsset:
    checks = max(len(violations), 1) if violations else 1
    passed = not violations
    score = 100.0 if passed else round(max(0.0, 100.0 * (1 - len(violations) / max(checks, len(violations)))), 2)
    if violations:
        score = 0.0
    return GovernanceAsset(
        kind=kind,
        name=name,
        path=str(path),
        passed=passed,
        score=100.0 if passed else score,
        violations=violations,
    )
