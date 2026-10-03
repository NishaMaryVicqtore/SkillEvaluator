"""Parse a skill pack's Markdown and YAML frontmatter into one instance."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
FENCE = re.compile(r"```(?:[^\n]*)\n(.*?)```", re.DOTALL)
SECRET = re.compile(
    r"(?i)(?:api[_-]?key|secret|password|access[_-]?token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{8,}"
    r"|BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY"
    r"|AKIA[0-9A-Z]{16}"
)


@dataclass
class LinkRef:
    href: str
    in_pack: bool
    exists: bool
    resolved: str


@dataclass
class ParsedSkill:
    path: Path
    root: Path
    frontmatter: dict
    body: str
    line_count: int
    headings: list[tuple[int, str]]
    sections: dict[str, str]
    links: list[LinkRef]
    pack_text: str
    files: dict[str, str] = field(default_factory=dict)

    @property
    def name(self) -> str:
        value = self.frontmatter.get("name", "")
        return value.strip() if isinstance(value, str) else ""

    @property
    def description(self) -> str:
        value = self.frontmatter.get("description", "")
        return value.strip() if isinstance(value, str) else ""

    @property
    def disable_model_invocation(self) -> bool:
        return self.frontmatter.get("disable-model-invocation") is True

    def h2(self) -> list[str]:
        return [title for level, title in self.headings if level == 2]

    def section(self, title: str) -> str:
        return self.sections.get(title.lower(), "")

    def section_prefix(self, prefix: str) -> str:
        prefix = prefix.lower()
        chunks = [text for title, text in self.sections.items() if title.startswith(prefix)]
        return "\n".join(chunks)

    def has_h2_prefix(self, prefix: str) -> bool:
        prefix = prefix.lower()
        return any(title.lower().startswith(prefix) for title in self.h2())

    def file_text(self, relative: str) -> str:
        return self.files.get(relative.replace("\\", "/"), "")


def parse_skill(path: Path) -> ParsedSkill:
    path = path.resolve()
    if path.is_dir():
        path = path / "SKILL.md"
    if not path.is_file():
        raise FileNotFoundError(f"Skill file not found: {path}")

    raw = path.read_text(encoding="utf-8-sig")
    frontmatter, body = _split_frontmatter(raw)
    headings = [(len(match.group(1)), match.group(2).strip()) for match in HEADING.finditer(body)]
    root = path.parent
    files = _read_pack(root)
    return ParsedSkill(
        path=path,
        root=root,
        frontmatter=frontmatter,
        body=body,
        line_count=len(raw.splitlines()) or 0,
        headings=headings,
        sections=_sections(body),
        links=_links(root, body),
        pack_text="\n".join(files.values()),
        files=files,
    )


def _split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise ValueError("SKILL.md must start with YAML frontmatter.")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("SKILL.md frontmatter is not closed with ---.")
    loaded = yaml.safe_load(parts[1]) or {}
    if not isinstance(loaded, dict):
        raise ValueError("SKILL.md frontmatter must be a mapping.")
    return loaded, parts[2].lstrip("\n")


def _sections(body: str) -> dict[str, str]:
    matches = list(HEADING.finditer(body))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group(2).strip().lower()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        text = body[start:end].strip()
        sections[title] = f"{sections[title]}\n{text}".strip() if title in sections else text
    return sections


def _read_pack(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for file in sorted(root.rglob("*.md")):
        if not file.is_file():
            continue
        relative = file.relative_to(root).as_posix()
        files[relative] = file.read_text(encoding="utf-8-sig")
    return files


def _links(root: Path, body: str) -> list[LinkRef]:
    refs: list[LinkRef] = []
    root_resolved = root.resolve()
    for href in LINK.findall(body):
        target = href.strip().split("#", 1)[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        candidate = (root / target.replace("\\", "/")).resolve()
        try:
            candidate.relative_to(root_resolved)
            in_pack = True
        except ValueError:
            in_pack = False
        refs.append(LinkRef(href=target, in_pack=in_pack, exists=candidate.is_file(), resolved=str(candidate)))
    return refs


def fenced_blocks(text: str) -> list[str]:
    return [match.group(1) for match in FENCE.finditer(text)]


def mode_vocabularies(parsed: ParsedSkill) -> dict[str, list[str]]:
    """Mode label sets named by the checklist, the universal workflow, and phase 0."""
    found: dict[str, list[str]] = {}
    sources = {
        "progress checklist": parsed.section_prefix("progress checklist"),
        "universal workflow": parsed.section_prefix("universal workflow"),
        "phase 0": parsed.section_prefix("phase 0"),
    }
    for source, text in sources.items():
        for line in text.splitlines():
            labels = _mode_labels(line)
            if labels:
                found[source] = labels
                break
    return found


def _mode_labels(line: str) -> list[str]:
    lowered = line.lower()
    if "mode" not in lowered and not re.search(r"greenfield|brownfield|new product", lowered):
        return []
    if "|" in line:
        parts = re.split(r"\|", line)
    elif line.count("/") >= 2:
        parts = line.split("/")
    else:
        return []
    labels: list[str] = []
    for part in parts:
        cleaned = re.sub(r"(?i)\bmode detect\b", "", part)
        cleaned = re.sub(r"^[\d.\s→>\-]+", "", cleaned)
        cleaned = re.sub(r"[`\[\]]", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:")
        if cleaned:
            labels.append(cleaned.lower())
    return labels


def conflicting_procedures(parsed: ParsedSkill) -> str | None:
    """Return a description when two procedures prescribe different artifacts."""
    second = [title for title in parsed.h2() if title.lower() in {"workflow", "phase detail"}]
    if not parsed.has_h2_prefix("universal workflow") or not second:
        return None
    universal = parsed.section_prefix("universal workflow")
    design_package = re.search(r"design package|draft package", universal, re.IGNORECASE)
    names_output = re.search(r"PRD\.md|BRD\.md|REQUIREMENTS_BASELINE", universal, re.IGNORECASE)
    other = "\n".join(parsed.section(title) for title in second)
    done = parsed.section_prefix("done when")
    other_names_output = re.search(r"PRD|BRD|Requirements Baseline", f"{other}\n{done}", re.IGNORECASE)
    if design_package and not names_output and other_names_output:
        names = ", ".join(second)
        return (
            f"Universal workflow stops at a design package. {names} tells the agent to write the document."
        )
    return None


def contains_secret(text: str) -> bool:
    return SECRET.search(text) is not None
