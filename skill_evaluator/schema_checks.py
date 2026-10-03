"""JSON Schema draft 2020-12 checks over a parsed skill pack."""

from __future__ import annotations

import re
from dataclasses import dataclass

from jsonschema import Draft202012Validator

from skill_evaluator.parse import (
    ParsedSkill,
    conflicting_procedures,
    contains_secret,
    fenced_blocks,
    mode_vocabularies,
)
from skill_evaluator.profiles import NFR_CATEGORIES, REQUIRED_H2, Profile

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@dataclass(frozen=True)
class Assertion:
    id: str
    aspect: str
    statement: str
    passed: bool
    detail: str


def build_assertions(parsed: ParsedSkill, profile: Profile) -> list[Assertion]:
    assertions = [
        _name(parsed),
        _description(parsed),
        _disable_invocation(parsed),
        _line_count(parsed),
        _required_h2(parsed),
        _announce(parsed),
        _silence(parsed),
        _risk_tier(parsed),
        _handoff(parsed, profile),
        _done_evidence(parsed),
        _forward_slashes(parsed),
        _secrets(parsed),
        _checklist_approval(parsed),
        _checklist_draft(parsed),
        _stop_blocks_finals(parsed),
        _subskills(parsed),
        _in_pack_links(parsed),
        _card_exists(parsed),
        _card_title(parsed),
        _one_mode_vocabulary(parsed),
        _single_procedure(parsed),
        _drafting_cites_template(parsed, profile),
        _template_headings(parsed, profile),
    ]
    assertions.extend(_profile_assertions(parsed, profile))
    return assertions


def validation_errors(assertions: list[Assertion]) -> list[str]:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["checks"],
        "properties": {
            "checks": {
                "type": "object",
                "required": [item.id for item in assertions],
                "properties": {item.id: {"const": True} for item in assertions},
                "additionalProperties": False,
            }
        },
    }
    Draft202012Validator.check_schema(schema)
    instance = {"checks": {item.id: item.passed for item in assertions}}
    validator = Draft202012Validator(schema)
    messages: list[str] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path)
        messages.append(f"{path}: {error.message}")
    return messages


def _result(check_id: str, aspect: str, statement: str, passed: bool, detail: str) -> Assertion:
    return Assertion(check_id, aspect, statement, passed, detail)


def _name(parsed: ParsedSkill) -> Assertion:
    passed = bool(KEBAB.match(parsed.name)) and len(parsed.name) <= 64
    detail = f"name is {parsed.name!r} ({len(parsed.name)} characters)."
    return _result("name_kebab", "job_relevance", "name is kebab-case and at most 64 characters", passed, detail)


def _description(parsed: ParsedSkill) -> Assertion:
    text = parsed.description
    reasons: list[str] = []
    if not 40 <= len(text) <= 1024:
        reasons.append(f"length {len(text)} is outside 40–1024")
    if not re.search(r"\bUse when\b", text):
        reasons.append('description does not contain "Use when"')
    first = text.split(None, 1)[0].lower() if text else ""
    if first in {"you", "your", "i", "we", "our"}:
        reasons.append("description starts in the first or second person")
    passed = not reasons
    detail = "Description is third person and states when to use the skill." if passed else "; ".join(reasons)
    return _result(
        "description_shape",
        "job_relevance",
        'description is 40–1024 characters, third person, and contains "Use when"',
        passed,
        detail,
    )


def _disable_invocation(parsed: ParsedSkill) -> Assertion:
    passed = parsed.disable_model_invocation
    return _result(
        "disable_model_invocation",
        "fluency",
        "disable-model-invocation is true",
        passed,
        "Frontmatter sets disable-model-invocation: true." if passed else "Frontmatter does not set it to true.",
    )


def _line_count(parsed: ParsedSkill) -> Assertion:
    passed = 1 <= parsed.line_count <= 500
    return _result(
        "line_count",
        "fluency",
        "SKILL.md is 1–500 lines",
        passed,
        f"SKILL.md is {parsed.line_count} lines.",
    )


def _required_h2(parsed: ParsedSkill) -> Assertion:
    missing = [title for title in REQUIRED_H2 if not parsed.has_h2_prefix(title)]
    passed = not missing
    detail = "Required H2 sections are present." if passed else "Missing: " + ", ".join(missing)
    return _result("required_h2", "fluency", "Required H2 sections are present", passed, detail)


def _announce(parsed: ParsedSkill) -> Assertion:
    expected = f"Running **/{parsed.name}**"
    passed = expected in parsed.body
    return _result(
        "announce",
        "actionability",
        f"Announce line contains `{expected}`",
        passed,
        "Announce line matches the skill name." if passed else f"Body does not contain {expected!r}.",
    )


def _silence(parsed: ParsedSkill) -> Assertion:
    gate = parsed.section_prefix("approval gate").lower()
    passed = "not" in gate and "approval" in gate
    return _result(
        "silence_not_approval",
        "governance",
        "Body says silence is not approval",
        passed,
        "Approval gate says silence is not approval." if passed else "Approval gate does not say silence is not approval.",
    )


def _risk_tier(parsed: ParsedSkill) -> Assertion:
    text = parsed.pack_text.lower()
    missing = [tier for tier in ("low", "medium", "high", "regulated") if not re.search(rf"\b{tier}\b", text)]
    passed = not missing
    detail = "Risk tier enum is present." if passed else "Missing: " + ", ".join(missing)
    return _result(
        "risk_tier_enum",
        "governance",
        "Risk tier enum low / medium / high / regulated is present",
        passed,
        detail,
    )


def _handoff(parsed: ParsedSkill, profile: Profile) -> Assertion:
    missing = [token for token in profile.handoff_tokens if token not in parsed.body]
    passed = not missing
    detail = "Hand-off names " + ", ".join(profile.handoff_tokens) if passed else "Missing: " + ", ".join(missing)
    return _result("handoff", "job_relevance", "Hand-off names the next skill", passed, detail)


def _done_evidence(parsed: ParsedSkill) -> Assertion:
    done = parsed.section_prefix("done when")
    passed = "evidence" in done.lower()
    return _result(
        "done_when_evidence",
        "fluency",
        "The Done when section mentions evidence",
        passed,
        "Done when mentions evidence." if passed else "The word evidence is not in the Done when section.",
    )


def _forward_slashes(parsed: ParsedSkill) -> Assertion:
    example = parsed.section_prefix("mini example")
    blocks = fenced_blocks(example)
    sample = "\n".join(blocks) if blocks else example
    passed = bool(sample.strip()) and "\\" not in sample
    detail = "Mini example uses forward slashes." if passed else "Mini example is missing or contains backslashes."
    return _result("forward_slashes", "actionability", "Mini example uses forward slashes", passed, detail)


def _secrets(parsed: ParsedSkill) -> Assertion:
    passed = not contains_secret(parsed.pack_text)
    return _result(
        "no_secrets",
        "governance",
        "No secret markers in the pack",
        passed,
        "No secret markers found." if passed else "A secret-shaped token is present in the pack.",
    )


def _checklist_approval(parsed: ParsedSkill) -> Assertion:
    checklist = parsed.section_prefix("progress checklist").lower()
    passed = "approval" in checklist
    return _result(
        "checklist_approval",
        "governance",
        "Checklist records explicit approval",
        passed,
        "Checklist names approval." if passed else "Progress checklist does not mention approval.",
    )


def _checklist_draft(parsed: ParsedSkill) -> Assertion:
    checklist = parsed.section_prefix("progress checklist").lower()
    passed = "draft" in checklist and ("post-approval" in checklist or "approval" in checklist)
    return _result(
        "checklist_draft_before_finals",
        "actionability",
        "Checklist drafts before finals",
        passed,
        "Checklist shows a draft before finals." if passed else "Checklist does not show a draft before approved finals.",
    )


def _stop_blocks_finals(parsed: ParsedSkill) -> Assertion:
    stop = parsed.section_prefix("stop conditions").lower()
    passed = "final" in stop or "do not write" in stop or "without explicit approval" in stop
    return _result(
        "stop_blocks_unapproved_finals",
        "governance",
        "Stop condition blocks unapproved finals",
        passed,
        "Stop conditions block an unapproved final." if passed else "Stop conditions do not mention finals or unapproved writes.",
    )


def _subskills(parsed: ParsedSkill) -> Assertion:
    links = [link for link in parsed.links if link.href.replace("\\", "/").startswith("subskills/")]
    bad: list[str] = []
    if not links:
        bad.append("no subskill links")
    for link in links:
        href = link.href.replace("\\", "/")
        if href.count("/") != 1 or not href.endswith(".md"):
            bad.append(f"{href} is deeper than one level")
        elif not link.exists:
            bad.append(f"{href} is missing")
    passed = not bad
    detail = f"{len(links)} subskill links resolve at depth 1." if passed else "; ".join(bad)
    return _result(
        "subskills_resolve",
        "actionability",
        "Subskill links exist, match subskills/*.md, and stay one level deep",
        passed,
        detail,
    )


def _in_pack_links(parsed: ParsedSkill) -> Assertion:
    in_pack = [link for link in parsed.links if link.in_pack]
    missing = [link.href for link in in_pack if not link.exists]
    passed = bool(in_pack) and not missing
    if not in_pack:
        detail = "SKILL.md has no in-pack relative links."
    elif missing:
        detail = "Missing: " + ", ".join(missing)
    else:
        detail = f"{len(in_pack)} in-pack links resolve."
    return _result("in_pack_links", "actionability", "In-pack reference and subskill links resolve", passed, detail)


def _card_exists(parsed: ParsedSkill) -> Assertion:
    passed = "SKILL_CARD.md" in parsed.files
    return _result(
        "skill_card_exists",
        "fluency",
        "SKILL_CARD.md exists",
        passed,
        "SKILL_CARD.md is in the pack." if passed else "SKILL_CARD.md is missing.",
    )


def _card_title(parsed: ParsedSkill) -> Assertion:
    expected = f"# SKILL_CARD — {parsed.name}"
    text = parsed.files.get("SKILL_CARD.md", "")
    if not text:
        return _result("skill_card_title", "fluency", "SKILL_CARD title is the canonical string with no BOM", False, "SKILL_CARD.md is missing.")
    raw = (parsed.root / "SKILL_CARD.md").read_bytes()
    first = text.splitlines()[0].strip("\ufeff") if text.splitlines() else ""
    problems: list[str] = []
    if raw.startswith(b"\xef\xbb\xbf"):
        problems.append("the file starts with a UTF-8 BOM")
    if first != expected:
        if "â€”" in first or "\u00e2\u20ac" in first:
            problems.append(f"the title is mojibake {first!r}")
        else:
            problems.append(f"the first line is {first!r}")
    passed = not problems
    detail = expected if passed else "Expected " + expected + ". " + "; ".join(problems).capitalize() + "."
    return _result(
        "skill_card_title",
        "fluency",
        f"SKILL_CARD title is exactly `{expected}` with no BOM",
        passed,
        detail,
    )


def _one_mode_vocabulary(parsed: ParsedSkill) -> Assertion:
    found = mode_vocabularies(parsed)
    sets = {tuple(labels) for labels in found.values()}
    passed = len(sets) <= 1
    if not found:
        detail = "No mode list is declared."
    elif passed:
        detail = "Mode labels agree: " + " | ".join(next(iter(found.values())))
    else:
        parts = [f"{source}: {' | '.join(labels)}" for source, labels in found.items()]
        detail = "Mode lists differ. " + "; ".join(parts)
    return _result(
        "one_mode_vocabulary",
        "coherence",
        "Checklist, phase 0, and the universal workflow use one mode vocabulary",
        passed,
        detail,
    )


def _single_procedure(parsed: ParsedSkill) -> Assertion:
    conflict = conflicting_procedures(parsed)
    passed = conflict is None
    detail = conflict or "The pack describes one procedure for the final document."
    return _result(
        "single_procedure",
        "coherence",
        "The pack has one procedure for the final document",
        passed,
        detail,
    )


def _drafting_cites_template(parsed: ParsedSkill, profile: Profile) -> Assertion:
    text = parsed.file_text(profile.drafting_relpath)
    passed = profile.template_filename in text
    detail = (
        f"{profile.drafting_relpath} cites {profile.template_filename}."
        if passed
        else f"{profile.drafting_relpath} does not contain {profile.template_filename}."
    )
    return _result(
        "drafting_cites_template",
        "coherence",
        f"{profile.drafting_relpath} points at {profile.template_filename}",
        passed,
        detail,
    )


def _template_headings(parsed: ParsedSkill, profile: Profile) -> Assertion:
    relative = f"references/{profile.template_filename}"
    text = parsed.file_text(relative).lower()
    if not text:
        return _result(
            "template_headings",
            "completeness",
            "Output template contains the required headings",
            False,
            f"{relative} is missing.",
        )
    missing = [label for label, needles in profile.template_groups if not any(needle in text for needle in needles)]
    passed = not missing
    detail = "Template headings match the output schema." if passed else "Missing headings: " + ", ".join(missing)
    return _result("template_headings", "completeness", "Output template contains the required headings", passed, detail)


def _profile_assertions(parsed: ParsedSkill, profile: Profile) -> list[Assertion]:
    if profile.id == "prd":
        return [_prd_intake(parsed), _prd_nfr(parsed), _prd_trace(parsed)]
    return [_brd_workflows(parsed), _brd_raci(parsed), _brd_gate(parsed)]


def _prd_intake(parsed: ParsedSkill) -> Assertion:
    text = parsed.file_text("subskills/intake.md").lower()
    needles = ("objective", "scope", "functional", "nfr", "acceptance", "constraint")
    missing = [needle for needle in needles if needle not in text]
    passed = bool(text) and not missing
    detail = "Intake lists the six baseline fields." if passed else "Missing from intake.md: " + ", ".join(missing or ["file"])
    return _result(
        "prd_intake_fields",
        "completeness",
        "intake.md lists objective, scope, functional IDs, NFRs, acceptance criteria, and constraints",
        passed,
        detail,
    )


def _prd_nfr(parsed: ParsedSkill) -> Assertion:
    text = parsed.file_text("references/prd-template.md").lower()
    missing = [name for name in NFR_CATEGORIES if name not in text]
    passed = not missing
    detail = "Template lists the structured NFR categories." if passed else "Missing categories: " + ", ".join(missing)
    return _result(
        "prd_structured_nfrs",
        "completeness",
        "PRD template lists structured NFR categories",
        passed,
        detail,
    )


def _prd_trace(parsed: ParsedSkill) -> Assertion:
    text = parsed.file_text("subskills/trace.md")
    passed = "REQ-" in text and "NFR-" in text
    return _result(
        "prd_trace_ids",
        "completeness",
        "trace.md keeps REQ-* and NFR-* identifiers",
        passed,
        "Trace subskill names REQ-* and NFR-*." if passed else "trace.md does not name both REQ-* and NFR-*.",
    )


def _brd_workflows(parsed: ParsedSkill) -> Assertion:
    text = (parsed.file_text("subskills/workflows.md") + "\n" + parsed.file_text("references/brd-template.md")).lower()
    missing = [name for name in ("happy", "alternate", "exception", "operational") if name not in text]
    passed = bool(parsed.file_text("subskills/workflows.md")) and not missing
    detail = "Workflow subskill and template name the four paths." if passed else "Missing: " + ", ".join(missing or ["workflows.md"])
    return _result(
        "brd_four_workflows",
        "completeness",
        "Workflows cover happy, alternate, exception, and operational paths",
        passed,
        detail,
    )


def _brd_raci(parsed: ParsedSkill) -> Assertion:
    text = parsed.file_text("references/brd-template.md").lower()
    passed = "raci" in text
    return _result(
        "brd_raci",
        "completeness",
        "BRD template includes a RACI",
        passed,
        "Template includes RACI." if passed else "brd-template.md does not mention RACI.",
    )


def _brd_gate(parsed: ParsedSkill) -> Assertion:
    text = parsed.file_text("subskills/gate.md").lower()
    passed = "approval" in text and ("architect" in text or "architecture" in text)
    return _result(
        "brd_architecture_gate",
        "governance",
        "gate.md blocks architecture finals until BRD approval",
        passed,
        "Gate holds architecture finals for BRD approval." if passed else "gate.md does not hold architecture finals for approval.",
    )
