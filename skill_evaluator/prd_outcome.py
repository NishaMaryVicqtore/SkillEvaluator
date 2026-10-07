"""Score a generated PRD against the PRD skill that was supposed to write it.

Schema checks compare the document with the skill's output template.
G-Eval scores whether those sections are filled, traceable, consistent, and testable.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from skill_evaluator.geval import CriterionScore
from skill_evaluator.parse import ParsedDocument, ParsedSkill, contains_secret, parse_document
from skill_evaluator.profiles import NFR_CATEGORIES, Profile
from skill_evaluator.schema_checks import Assertion, validation_errors

PRD_WEIGHTS = {
    "contract_coverage": 0.25,
    "traceability": 0.20,
    "coherence": 0.20,
    "governance": 0.15,
    "testability": 0.20,
}

_ID = re.compile(r"\b(?:REQ|NFR|AC)-[A-Za-z0-9]+\b")
_TIERS = ("low", "medium", "high", "regulated")
_TESTABLE = re.compile(
    r"(?i)\b(shall|must|should|will|shows|sends|returns|displays|records|creates|blocks|equals|within|when|given)\b"
)


@dataclass
class ArtifactResult:
    path: str
    assertions: list[Assertion]
    criteria: list[CriterionScore]
    schema_errors: list[str]


def score_brd(parsed: ParsedSkill, profile: Profile, brd_path) -> ArtifactResult:
    document = parse_document(brd_path)
    assertions = _brd_assertions(profile, document)
    criteria = _brd_criteria(profile, document)
    return ArtifactResult(
        path=str(document.path),
        assertions=assertions,
        criteria=criteria,
        schema_errors=validation_errors(assertions),
    )


def score_prd(parsed: ParsedSkill, profile: Profile, prd_path) -> ArtifactResult:
    document = parse_document(prd_path)
    assertions = _assertions(parsed, profile, document)
    criteria = _criteria(profile, document)
    return ArtifactResult(
        path=str(document.path),
        assertions=assertions,
        criteria=criteria,
        schema_errors=validation_errors(assertions),
    )


def _assertions(parsed: ParsedSkill, profile: Profile, document: ParsedDocument) -> list[Assertion]:
    checks = [_heading(document, label, needles) for label, needles in profile.template_groups]
    checks.extend(
        [
            _req_ids(document),
            _nfr_ids(document),
            _nfr_categories(parsed, profile, document),
            _trace_cites(document),
            _unique_ids(document),
            _risk_tier(document),
            _approval(document),
            _secrets(document),
            _acceptance(document),
        ]
    )
    return checks


def _heading(document: ParsedDocument, label: str, needles: tuple[str, ...]) -> Assertion:
    body = _section(document, needles)
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    passed = body is not None
    detail = f"{label} is present." if passed else f"The PRD has no heading for {label}."
    return Assertion(f"heading_{slug}", "contract_coverage", f"PRD includes {label}", passed, detail)


def _req_ids(document: ParsedDocument) -> Assertion:
    found = _ids(document.text, "REQ")
    passed = bool(found)
    detail = f"Found {len(found)} REQ identifiers." if passed else "The PRD has no REQ-* identifier."
    return Assertion("req_ids", "traceability", "PRD contains at least one REQ-* identifier", passed, detail)


def _nfr_ids(document: ParsedDocument) -> Assertion:
    found = _ids(document.text, "NFR")
    passed = bool(found)
    detail = f"Found {len(found)} NFR identifiers." if passed else "The PRD has no NFR-* identifier."
    return Assertion("nfr_ids", "contract_coverage", "PRD contains at least one NFR-* identifier", passed, detail)


def _nfr_categories(parsed: ParsedSkill, profile: Profile, document: ParsedDocument) -> Assertion:
    template = parsed.file_text(f"references/{profile.template_filename}").lower()
    required = [name for name in NFR_CATEGORIES if name in template]
    missing = [name for name in required if name not in document.text.lower()]
    if not required:
        return Assertion(
            "nfr_categories",
            "contract_coverage",
            "PRD covers the NFR categories named by the skill template",
            True,
            "The skill template names no NFR categories.",
        )
    passed = not missing
    detail = "NFR categories from the skill template appear in the PRD." if passed else "Missing: " + ", ".join(missing)
    return Assertion(
        "nfr_categories",
        "contract_coverage",
        "PRD covers the NFR categories named by the skill template",
        passed,
        detail,
    )


def _trace_cites(document: ParsedDocument) -> Assertion:
    functional = _section(document, ("functional requirement",)) or ""
    trace = _section(document, ("traceability",))
    required = _ids(functional, "REQ")
    if trace is None:
        return Assertion(
            "trace_cites_reqs",
            "traceability",
            "Traceability cites every functional REQ identifier",
            False,
            "The PRD has no traceability section.",
        )
    missing = [item for item in required if item not in trace]
    passed = bool(required) and not missing
    if not required:
        detail = "The functional requirements section has no REQ identifier to trace."
    elif passed:
        detail = "Every functional REQ identifier appears in traceability."
    else:
        detail = "Not traced: " + ", ".join(missing)
    return Assertion(
        "trace_cites_reqs",
        "traceability",
        "Traceability cites every functional REQ identifier",
        passed,
        detail,
    )


def _unique_ids(document: ParsedDocument) -> Assertion:
    functional = _section(document, ("functional requirement",)) or ""
    nonfunctional = _section(document, ("non-functional requirement",)) or ""
    duplicates = _duplicates(functional) + _duplicates(nonfunctional)
    passed = not duplicates
    detail = "Requirement identifiers are unique." if passed else "Repeated: " + ", ".join(duplicates)
    return Assertion("unique_requirement_ids", "coherence", "REQ and NFR identifiers are unique", passed, detail)


def _risk_tier(document: ParsedDocument) -> Assertion:
    selected = _selected_tier(document.text)
    passed = selected is not None
    detail = f"Risk tier is {selected}." if passed else "Risk tier is missing or still lists more than one tier."
    return Assertion("risk_tier_selected", "governance", "PRD selects one risk tier", passed, detail)


def _approval(document: ParsedDocument) -> Assertion:
    body = _section(document, ("approval record",))
    passed = bool(body and body.strip())
    detail = "Approval record is present." if passed else "Approval record is missing or empty."
    return Assertion("approval_record", "governance", "PRD includes an approval record", passed, detail)


def _secrets(document: ParsedDocument) -> Assertion:
    passed = not contains_secret(document.text)
    detail = "No secret markers found." if passed else "A secret-shaped token is present in the PRD."
    return Assertion("prd_no_secrets", "governance", "PRD contains no secret markers", passed, detail)


def _acceptance(document: ParsedDocument) -> Assertion:
    body = _section(document, ("acceptance criteria",))
    passed = bool(body and body.strip())
    detail = "Acceptance criteria section is present." if passed else "Acceptance criteria section is missing or empty."
    return Assertion("acceptance_section", "testability", "PRD includes acceptance criteria", passed, detail)


def _criteria(profile: Profile, document: ParsedDocument) -> list[CriterionScore]:
    return [
        _coverage(profile, document),
        _traceability(document),
        _coherence(profile, document),
        _governance(document),
        _testability(document),
    ]


def _coverage(profile: Profile, document: ParsedDocument) -> CriterionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    for label, needles in profile.template_groups:
        body = _section(document, needles)
        if body is None:
            gaps.append(f"{label} is missing.")
        elif not _has_substance(body):
            gaps.append(f"{label} has a heading and no content.")
        else:
            evidence.append(f"{label} has content.")
    requirement = "Every section required by the skill template is present and filled in."
    return _score("contract_coverage", "Contract coverage", _band(len(gaps)), requirement, evidence, gaps)


def _traceability(document: ParsedDocument) -> CriterionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    functional = _section(document, ("functional requirement",)) or ""
    trace = _section(document, ("traceability",))
    reqs = _ids(functional, "REQ")
    nfrs = _ids(_section(document, ("non-functional requirement",)) or "", "NFR")
    if not reqs:
        gaps.append("The functional requirements section has no REQ identifier.")
        score = 1
    elif trace is None:
        gaps.append("Traceability section is missing.")
        score = 2
    else:
        missing = [item for item in reqs if item not in trace]
        if not missing and nfrs:
            evidence.append("Every functional REQ identifier is cited in traceability, and the PRD has NFR identifiers.")
            score = 5
        elif not missing:
            evidence.append("Every functional REQ identifier is cited in traceability.")
            gaps.append("The PRD has no NFR identifier.")
            score = 4
        elif len(missing) <= len(reqs) / 2:
            gaps.append("Traceability omits " + ", ".join(missing) + ".")
            score = 3
        else:
            gaps.append("Traceability omits " + ", ".join(missing) + ".")
            score = 2
    requirement = "Functional REQ identifiers reappear in traceability, and the PRD names NFR identifiers."
    return _score("traceability", "Traceability", score, requirement, evidence, gaps)


def _coherence(profile: Profile, document: ParsedDocument) -> CriterionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    functional = _section(document, ("functional requirement",)) or ""
    nonfunctional = _section(document, ("non-functional requirement",)) or ""
    duplicates = _duplicates(functional) + _duplicates(nonfunctional)
    reqs = _ids(document.text, "REQ")
    nfrs = _ids(document.text, "NFR")
    approval = _section(document, ("approval record",)) or ""
    approved = bool(re.search(r"\bapproved\b", approval, re.IGNORECASE))
    empty = [
        label
        for label, needles in profile.template_groups
        if _section(document, needles) is not None and not _has_substance(_section(document, needles) or "")
    ]
    if not reqs and not nfrs:
        gaps.append("The PRD has no REQ or NFR identifiers to keep consistent.")
        score = 2
    else:
        if duplicates:
            gaps.append("Repeated identifiers: " + ", ".join(duplicates) + ".")
        else:
            evidence.append("REQ and NFR identifiers are unique inside their sections.")
        if approved and empty:
            gaps.append("Approval says approved while these sections are empty: " + ", ".join(empty) + ".")
        elif not empty:
            evidence.append("Filled sections are not left as placeholders.")
        if duplicates and approved and empty:
            score = 2
        elif duplicates or (approved and len(empty) >= 2):
            score = 3
        elif empty or (approved and empty):
            score = 4
        else:
            score = 5
    requirement = "Requirement identifiers are unique, and an approved PRD does not still contain empty sections."
    return _score("coherence", "Coherence", score, requirement, evidence, gaps)


def _governance(document: ParsedDocument) -> CriterionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    selected = _selected_tier(document.text)
    approval = _section(document, ("approval record",)) or ""
    if selected:
        evidence.append(f"Risk tier is {selected}.")
    else:
        gaps.append("Risk tier is missing or still offers more than one tier.")
    if _has_substance(approval) and re.search(r"\b(approved|draft)\b", approval, re.IGNORECASE):
        evidence.append("The approval record states approved or draft.")
    else:
        gaps.append("The approval record does not state approved or draft.")
    if re.search(r"\b20\d{2}-\d{2}-\d{2}\b", approval):
        evidence.append("The approval record has a date.")
    else:
        gaps.append("The approval record has no date.")
    if contains_secret(document.text):
        gaps.append("A secret-shaped token is present.")
    else:
        evidence.append("The PRD has no secret markers.")
    requirement = "The PRD selects one risk tier and records an approval status and date, with no secrets."
    return _score("governance", "Governance", _band(len(gaps)), requirement, evidence, gaps)


def _testability(document: ParsedDocument) -> CriterionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    body = _section(document, ("acceptance criteria",)) or ""
    lines = _criterion_lines(body)
    if not lines:
        gaps.append("Acceptance criteria section has no criteria.")
        score = 1
    else:
        testable = [line for line in lines if _TESTABLE.search(line) and "tbd" not in line.lower() and len(line) >= 20]
        ratio = len(testable) / len(lines)
        if ratio == 1:
            evidence.append(f"All {len(lines)} acceptance criteria name an observable outcome.")
            score = 5
        elif ratio >= 0.75:
            evidence.append(f"{len(testable)} of {len(lines)} acceptance criteria are testable.")
            gaps.append("At least one acceptance criterion is still a placeholder.")
            score = 4
        elif ratio >= 0.5:
            gaps.append(f"Only {len(testable)} of {len(lines)} acceptance criteria are testable.")
            score = 3
        elif ratio > 0:
            gaps.append(f"Only {len(testable)} of {len(lines)} acceptance criteria are testable.")
            score = 2
        else:
            gaps.append("Acceptance criteria do not name an observable outcome.")
            score = 1
    requirement = "Each acceptance criterion states an observable outcome."
    return _score("testability", "Testability", score, requirement, evidence, gaps)


def _score(
    criterion_id: str,
    criterion: str,
    score: int,
    requirement: str,
    evidence: list[str],
    gaps: list[str],
) -> CriterionScore:
    return CriterionScore(
        criterion_id,
        criterion,
        PRD_WEIGHTS[criterion_id],
        min(5, max(1, score)),
        requirement,
        tuple(evidence),
        tuple(gaps),
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


def _section(document: ParsedDocument, needles: tuple[str, ...]) -> str | None:
    for title, body in document.sections.items():
        if any(needle in title for needle in needles):
            return body
    return None


def _has_substance(body: str) -> bool:
    kept: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or re.fullmatch(r"[\|\s:\-]+", stripped):
            continue
        if stripped.lower() in {"tbd", "todo", "n/a", "..."}:
            continue
        kept.append(stripped)
    letters = re.sub(r"[^A-Za-z0-9]", "", " ".join(kept))
    return len(letters) >= 40


def _ids(text: str, prefix: str) -> list[str]:
    return [item for item in _ID.findall(text) if item.startswith(prefix + "-")]


def _duplicates(text: str) -> list[str]:
    counts = Counter(_ID.findall(text))
    return sorted(item for item, count in counts.items() if count > 1)


def _selected_tier(text: str) -> str | None:
    for line in text.splitlines():
        if "risk tier" not in line.lower():
            continue
        found = [tier for tier in _TIERS if re.search(rf"\b{tier}\b", line, re.IGNORECASE)]
        if len(found) == 1:
            return found[0]
        return None
    return None


def _brd_assertions(profile: Profile, document: ParsedDocument) -> list[Assertion]:
    checks = []
    for label, needles in profile.template_groups:
        body = _section(document, needles)
        slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
        passed = body is not None
        detail = f"{label} is present." if passed else f"The BRD has no heading for {label}."
        checks.append(Assertion(f"heading_{slug}", "contract_coverage", f"BRD includes {label}", passed, detail))
    checks.append(_brd_workflows(document))
    checks.append(_brd_raci(document))
    checks.append(_brd_trace(document))
    selected = _selected_tier(document.text)
    checks.append(
        Assertion(
            "risk_tier_selected",
            "governance",
            "BRD selects one risk tier",
            selected is not None,
            f"Risk tier is {selected}." if selected else "Risk tier is missing or still lists more than one tier.",
        )
    )
    approval = _section(document, ("approval record",))
    checks.append(
        Assertion(
            "approval_record",
            "governance",
            "BRD includes an approval record",
            bool(approval and approval.strip()),
            "Approval record is present." if approval and approval.strip() else "Approval record is missing or empty.",
        )
    )
    secret = contains_secret(document.text)
    checks.append(
        Assertion(
            "brd_no_secrets",
            "governance",
            "BRD contains no secret markers",
            not secret,
            "No secret markers found." if not secret else "A secret-shaped token is present in the BRD.",
        )
    )
    acceptance = _section(document, ("acceptance", "business workflow", "happy"))
    checks.append(
        Assertion(
            "acceptance_section",
            "testability",
            "BRD includes a workflow or acceptance section that can be tested",
            bool(acceptance and acceptance.strip()),
            "A workflow or acceptance section is present." if acceptance and acceptance.strip() else "No workflow or acceptance section was found.",
        )
    )
    return checks


def _brd_workflows(document: ParsedDocument) -> Assertion:
    missing = [name for name in ("happy", "alternate", "exception", "operational") if _section(document, (name,)) is None]
    passed = not missing
    detail = "Happy, alternate, exception, and operational paths are present." if passed else "Missing: " + ", ".join(missing) + "."
    return Assertion("four_workflows", "contract_coverage", "BRD covers four workflow types", passed, detail)


def _brd_raci(document: ParsedDocument) -> Assertion:
    body = _section(document, ("raci",))
    passed = bool(body and re.search(r"(?i)\b(responsible|accountable|consulted|informed)\b", body))
    detail = "RACI names a responsibility." if passed else "RACI section is missing or does not name a responsibility."
    return Assertion("raci_named", "governance", "BRD names RACI responsibilities", passed, detail)


def _brd_trace(document: ParsedDocument) -> Assertion:
    body = _section(document, ("traceability",)) or ""
    passed = "prd" in body.lower() or bool(_ids(body, "REQ"))
    detail = "Traceability cites the PRD." if passed else "Traceability does not cite the PRD."
    return Assertion("trace_cites_prd", "traceability", "Traceability cites the PRD", passed, detail)


def _brd_criteria(profile: Profile, document: ParsedDocument) -> list[CriterionScore]:
    return [
        _coverage(profile, document),
        _brd_traceability(document),
        _brd_coherence(profile, document),
        _brd_governance(document),
        _brd_testability(document),
    ]


def _brd_traceability(document: ParsedDocument) -> CriterionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    trace = _section(document, ("traceability",))
    if trace is None:
        gaps.append("Traceability section is missing.")
        score = 1
    elif "prd" not in trace.lower() and not _ids(trace, "REQ"):
        gaps.append("Traceability does not cite the PRD or a REQ identifier.")
        score = 2
    elif not _has_substance(trace):
        gaps.append("Traceability has a heading and no content.")
        score = 3
    else:
        evidence.append("Traceability cites the source PRD.")
        score = 5
    return _score("traceability", "Traceability", score, "The BRD traces its workflows back to the approved PRD.", evidence, gaps)


def _brd_coherence(profile: Profile, document: ParsedDocument) -> CriterionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    approval = _section(document, ("approval record",)) or ""
    approved = bool(re.search(r"\bapproved\b", approval, re.IGNORECASE))
    empty = [
        label
        for label, needles in profile.template_groups
        if _section(document, needles) is not None and not _has_substance(_section(document, needles) or "")
    ]
    if empty:
        gaps.append("Empty sections: " + ", ".join(empty) + ".")
    else:
        evidence.append("Filled sections are not left as placeholders.")
    if approved and empty:
        gaps.append("Approval says approved while sections are still empty.")
        score = 3 if len(empty) == 1 else 2
    elif empty:
        score = 4 if len(empty) == 1 else 3
    else:
        score = 5
    return _score("coherence", "Coherence", score, "An approved BRD does not still contain empty sections.", evidence, gaps)


def _brd_governance(document: ParsedDocument) -> CriterionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    selected = _selected_tier(document.text)
    approval = _section(document, ("approval record",)) or ""
    if selected:
        evidence.append(f"Risk tier is {selected}.")
    else:
        gaps.append("Risk tier is missing or still offers more than one tier.")
    if _has_substance(approval) and re.search(r"\b(approved|draft)\b", approval, re.IGNORECASE):
        evidence.append("The approval record states approved or draft.")
    else:
        gaps.append("The approval record does not state approved or draft.")
    if re.search(r"\b20\d{2}-\d{2}-\d{2}\b", approval):
        evidence.append("The approval record has a date.")
    else:
        gaps.append("The approval record has no date.")
    if contains_secret(document.text):
        gaps.append("A secret-shaped token is present.")
    else:
        evidence.append("The BRD has no secret markers.")
    return _score(
        "governance",
        "Governance",
        _band(len(gaps)),
        "The BRD selects one risk tier and records an approval status and date, with no secrets.",
        evidence,
        gaps,
    )


def _brd_testability(document: ParsedDocument) -> CriterionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    chunks = [
        _section(document, needle) or ""
        for needle in (("happy",), ("alternate",), ("exception",), ("operational",), ("acceptance",))
    ]
    lines = [line for chunk in chunks for line in _criterion_lines(chunk)]
    if not lines:
        gaps.append("Workflow sections have no steps.")
        score = 1
    else:
        testable = [line for line in lines if _TESTABLE.search(line) and "tbd" not in line.lower() and len(line) >= 20]
        ratio = len(testable) / len(lines)
        if ratio >= 0.75:
            evidence.append(f"{len(testable)} of {len(lines)} workflow lines name an observable outcome.")
            score = 5 if ratio == 1 else 4
        elif ratio >= 0.5:
            gaps.append(f"Only {len(testable)} of {len(lines)} workflow lines are testable.")
            score = 3
        elif ratio > 0:
            gaps.append(f"Only {len(testable)} of {len(lines)} workflow lines are testable.")
            score = 2
        else:
            gaps.append("Workflow lines do not name an observable outcome.")
            score = 1
    return _score("testability", "Testability", score, "Each workflow step states an observable outcome.", evidence, gaps)


def _criterion_lines(body: str) -> list[str]:
    lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or re.fullmatch(r"\|?[\s\-:|]+", stripped):
            continue
        if stripped.startswith(("#",)):
            continue
        lines.append(stripped)
    return lines
