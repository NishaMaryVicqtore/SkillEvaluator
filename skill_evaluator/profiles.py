"""PRD and BRD skill profiles.

Criteria follow the static G-Eval used on /grill: job relevance, coherence,
output-contract completeness, actionability, governance, and fluency.
Schema checks follow the Markdown-to-JSON draft 2020-12 review of that pack.
"""

from __future__ import annotations

from dataclasses import dataclass

WEIGHTS = {
    "job_relevance": 0.20,
    "coherence": 0.20,
    "completeness": 0.25,
    "actionability": 0.15,
    "governance": 0.15,
    "fluency": 0.05,
}


@dataclass(frozen=True)
class Profile:
    id: str
    skill_label: str
    job_requirement: str
    output_path: str
    handoff_tokens: tuple[str, ...]
    template_filename: str
    drafting_relpath: str
    completeness: tuple[tuple[str, str], ...]
    template_groups: tuple[tuple[str, tuple[str, ...]], ...]


PRD = Profile(
    id="prd",
    skill_label="/prd",
    job_requirement=(
        "A skill whose job is to write a Product Requirements Document from a "
        "requirements baseline, and to hand that document to /brd or /architect."
    ),
    output_path="prd/PRD.md",
    handoff_tokens=("/brd",),
    template_filename="prd-template.md",
    drafting_relpath="subskills/draft.md",
    completeness=(
        ("objective", "objective"),
        ("scope", "scope"),
        ("functional IDs", "functional"),
        ("non-functional requirements", "nfr"),
        ("acceptance criteria", "acceptance criteria"),
        ("constraints", "constraint"),
        ("problem statement", "problem statement"),
        ("user journeys", "user journey"),
        ("traceability", "traceability"),
        ("risk tier", "risk tier"),
        ("approval record", "approval"),
        ("hand-off to /brd", "/brd"),
    ),
    template_groups=(
        ("Overview", ("overview",)),
        ("Problem statement", ("problem statement",)),
        ("Goals and non-goals", ("goals",)),
        ("Users and personas", ("users", "personas")),
        ("User journeys", ("user journey",)),
        ("Functional requirements", ("functional requirement",)),
        ("Non-functional requirements", ("non-functional requirement",)),
        ("Acceptance criteria", ("acceptance criteria",)),
        ("Traceability", ("traceability",)),
        ("Approval record", ("approval record",)),
    ),
)

BRD = Profile(
    id="brd",
    skill_label="/brd",
    job_requirement=(
        "A skill whose job is to write a Business Requirements Document from an "
        "approved PRD, cover happy, alternate, exception, and operational workflows, "
        "and block architecture finals until BRD approval is recorded."
    ),
    output_path="brd/BRD.md",
    handoff_tokens=("/prd", "/architect"),
    template_filename="brd-template.md",
    drafting_relpath="subskills/package.md",
    completeness=(
        ("approved PRD input", "approved prd"),
        ("happy path", "happy"),
        ("alternate path", "alternate"),
        ("exception path", "exception"),
        ("operational path", "operational"),
        ("RACI", "raci"),
        ("compliance or audit", "compliance"),
        ("business rules", "business rule"),
        ("trace to the PRD", "prd"),
        ("risk tier", "risk tier"),
        ("architecture held for approval", "/architect"),
        ("approval record", "approval"),
    ),
    template_groups=(
        ("Overview", ("overview",)),
        ("Business objectives", ("business objective",)),
        ("Scope and boundaries", ("scope",)),
        ("Stakeholders and RACI", ("raci",)),
        ("Business workflows", ("business workflow",)),
        ("Happy paths", ("happy",)),
        ("Alternate paths", ("alternate",)),
        ("Exception paths", ("exception",)),
        ("Operational paths", ("operational",)),
        ("Business rules", ("business rule",)),
        ("Compliance, audit, and retention", ("compliance",)),
        ("Traceability to PRD", ("traceability",)),
        ("Approval record", ("approval record",)),
    ),
)

PROFILES = {"prd": PRD, "brd": BRD}

NFR_CATEGORIES = (
    "availability",
    "latency",
    "capacity",
    "resilience",
    "accessibility",
    "localization",
    "observability",
    "privacy",
)

REQUIRED_H2 = (
    "when to use",
    "when not to use",
    "execution contract",
    "universal workflow",
    "approval gate",
    "subskills",
    "references",
    "done when",
)


def detect_profile(name: str, body: str, requested: str) -> Profile:
    if requested in PROFILES:
        return PROFILES[requested]
    lowered = body.lower()
    if name == "prd" or ("product requirements" in lowered and "business requirements document" not in lowered):
        return PRD
    if name == "brd" or "business requirements document" in lowered:
        return BRD
    raise ValueError(
        "This framework evaluates skills that generate a PRD or a BRD. "
        f"Could not tell which from name {name!r}. Pass --profile prd or --profile brd."
    )
