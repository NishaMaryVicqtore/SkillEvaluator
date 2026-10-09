import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from tse.models import SkillMetadata, Tier1Result


VALID_TID_SCOPE_PREFIXES = (
    "connect.",
    "tekla.",
    "projectsight.",
    "geospatial.",
)

SECRET_PATTERNS = (
    (
        "Bearer token",
        re.compile(
            r"\bbearer\s+eyJ[A-Za-z0-9._-]{4,}",
            re.IGNORECASE,
        ),
    ),
    ("OpenAI-style API key", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{4,}")),
    ("Trimble secret", re.compile(r"\btid_secret_[A-Za-z0-9_-]{4,}", re.IGNORECASE)),
    (
        "API key assignment",
        re.compile(r"\bapi_key\s*=\s*[\"']?[^\s\"']{4,}", re.IGNORECASE),
    ),
    ("Private key", re.compile(r"-----BEGIN PRIVATE KEY-----")),
)

PROMPT_INJECTION_PATTERNS = (
    (
        "ignore previous instructions",
        re.compile(r"\bignore\s+(?:all\s+)?previous\s+instructions\b", re.IGNORECASE),
    ),
    (
        "ignore all instructions",
        re.compile(r"\bignore\s+all\s+instructions\b", re.IGNORECASE),
    ),
    (
        "system prompt override",
        re.compile(r"\bsystem\s+prompt\s+override\b", re.IGNORECASE),
    ),
    (
        "bypass authorization",
        re.compile(r"\bbypass\s+authorization\b", re.IGNORECASE),
    ),
    (
        "dump tenant data",
        re.compile(r"\bdump\s+tenant\s+data\b", re.IGNORECASE),
    ),
)


def _display_path(path: Path, skill_dir: Path) -> str:
    try:
        return path.relative_to(skill_dir).as_posix()
    except ValueError:
        return path.as_posix()


def _read_text(path: Path, skill_dir: Path, violations: list[str]) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        violations.append(
            f"Unable to read {_display_path(path, skill_dir)}: {exc.__class__.__name__}"
        )
        return None


def _load_metadata(
    metadata_path: Path,
    skill_dir: Path,
    violations: list[str],
) -> dict[str, object] | None:
    text = _read_text(metadata_path, skill_dir, violations)
    if text is None:
        return None

    try:
        raw_metadata = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        violations.append(f"metadata.yaml is not valid YAML: {exc}")
        return None

    if not isinstance(raw_metadata, dict):
        violations.append("metadata.yaml must contain a YAML mapping")
        return None

    try:
        metadata = SkillMetadata.model_validate(raw_metadata)
    except ValidationError as exc:
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"]) or "metadata"
            violations.append(
                f"metadata.yaml schema error at {location}: {error['msg']}"
            )
    else:
        if not metadata.author.strip():
            violations.append("metadata.yaml author must not be empty")

    return raw_metadata


def _check_scopes(raw_metadata: dict[str, object], violations: list[str]) -> None:
    scopes = raw_metadata.get("tid_scopes_required")
    if not isinstance(scopes, list):
        return

    for scope in scopes:
        if not isinstance(scope, str):
            continue
        if not scope.startswith(VALID_TID_SCOPE_PREFIXES):
            prefixes = ", ".join(VALID_TID_SCOPE_PREFIXES)
            violations.append(
                f"Invalid TID scope '{scope}': expected one of these prefixes: {prefixes}"
            )


def _scan_files(skill_dir: Path, violations: list[str]) -> dict[Path, str]:
    metadata_path = skill_dir / "metadata.yaml"
    skill_path = skill_dir / "SKILL.md"
    candidates = {metadata_path, skill_path}

    for path in skill_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".py", ".json"}:
            candidates.add(path)

    contents: dict[Path, str] = {}
    for path in sorted(candidates, key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        text = _read_text(path, skill_dir, violations)
        if text is None:
            continue
        contents[path] = text

        for secret_name, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                violations.append(
                    f"Hardcoded {secret_name} detected in "
                    f"{_display_path(path, skill_dir)}"
                )

    return contents


def _scan_prompt_injection(
    skill_path: Path,
    skill_text: str,
    skill_dir: Path,
    violations: list[str],
) -> None:
    for phrase, pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(skill_text):
            violations.append(
                f"Prompt injection phrase '{phrase}' detected in "
                f"{_display_path(skill_path, skill_dir)}"
            )


def run_tier1_scan(skill_dir: Path) -> Tier1Result:
    """Run deterministic, offline Tier 1 checks against a skill directory."""
    skill_dir = Path(skill_dir)
    violations: list[str] = []

    if not skill_dir.is_dir():
        return Tier1Result(
            passed=False,
            violations=[f"Skill directory does not exist: {skill_dir}"],
        )

    metadata_path = skill_dir / "metadata.yaml"
    if not metadata_path.is_file():
        violations.append("metadata.yaml is missing")
    else:
        raw_metadata = _load_metadata(metadata_path, skill_dir, violations)
        if raw_metadata is not None:
            _check_scopes(raw_metadata, violations)

    skill_path = skill_dir / "SKILL.md"
    if not skill_path.is_file():
        violations.append("SKILL.md is missing")

    contents = _scan_files(skill_dir, violations)
    skill_text = contents.get(skill_path)
    if skill_text is not None:
        _scan_prompt_injection(skill_path, skill_text, skill_dir, violations)

    return Tier1Result(passed=not violations, violations=violations)
