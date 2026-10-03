"""Form-filled G-Eval for a PRD or BRD skill pack.

The procedure is the one used in the Grill skill review: state the criterion,
collect evidence, note gaps, then assign an integer from 1 to 5. Token log
probabilities are not available, so the score is the integer from this form.
"""

from __future__ import annotations

from dataclasses import dataclass

from skill_evaluator.parse import ParsedSkill, conflicting_procedures, mode_vocabularies
from skill_evaluator.profiles import WEIGHTS, Profile


@dataclass(frozen=True)
class CriterionScore:
    id: str
    criterion: str
    weight: float
    score: int
    requirement: str
    evidence: tuple[str, ...]
    gaps: tuple[str, ...]

    @property
    def normalized(self) -> float:
        return (self.score - 1) / 4


def score_criteria(parsed: ParsedSkill, profile: Profile) -> list[CriterionScore]:
    return [
        _job_relevance(parsed, profile),
        _coherence(parsed, profile),
        _completeness(parsed, profile),
        _actionability(parsed, profile),
        _governance(parsed, profile),
        _fluency(parsed, profile),
    ]


def _criterion(
    criterion_id: str,
    criterion: str,
    score: int,
    requirement: str,
    evidence: list[str],
    gaps: list[str],
) -> CriterionScore:
    clamped = min(5, max(1, score))
    return CriterionScore(criterion_id, criterion, WEIGHTS[criterion_id], clamped, requirement, tuple(evidence), tuple(gaps))


def _from_missing(missing: int) -> int:
    if missing <= 0:
        return 5
    if missing == 1:
        return 4
    if missing == 2:
        return 3
    if missing == 3:
        return 2
    return 1


def _job_relevance(parsed: ParsedSkill, profile: Profile) -> CriterionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    if re_use_when(parsed.description):
        evidence.append("The description states the job and includes a Use when trigger.")
    else:
        gaps.append("The description does not say when to invoke the skill.")
    if parsed.has_h2_prefix("when to use") and parsed.has_h2_prefix("when not to use"):
        evidence.append("When to use and When NOT to use bound the job.")
    else:
        gaps.append("When to use or When NOT to use is missing.")
    if profile.output_path in parsed.pack_text:
        evidence.append(f"The default output path {profile.output_path} is named.")
    else:
        gaps.append(f"The default output path {profile.output_path} is not named.")
    missing_handoff = [token for token in profile.handoff_tokens if token not in parsed.body]
    if not missing_handoff:
        evidence.append("The hand-off names " + ", ".join(profile.handoff_tokens) + ".")
    else:
        gaps.append("Hand-off is missing " + ", ".join(missing_handoff) + ".")
    return _criterion("job_relevance", "Job relevance", _from_missing(len(gaps)), profile.job_requirement, evidence, gaps)


def re_use_when(description: str) -> bool:
    return "use when" in description.lower()


def _coherence(parsed: ParsedSkill, profile: Profile) -> CriterionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    if not parsed.has_h2_prefix("universal workflow") and not parsed.has_h2_prefix("workflow"):
        gaps.append("The pack has no procedure the agent can follow.")
        return _criterion("coherence", "Coherence", 1, _coherence_requirement(profile), evidence, gaps)

    conflict = conflicting_procedures(parsed)
    modes = mode_vocabularies(parsed)
    mode_sets = {tuple(labels) for labels in modes.values()}
    template_cited = profile.template_filename in parsed.file_text(profile.drafting_relpath)

    if conflict:
        gaps.append(conflict)
    else:
        evidence.append("One procedure tells the agent which document to write.")
    if len(mode_sets) > 1:
        rendered = "; ".join(f"{source}: {' | '.join(labels)}" for source, labels in modes.items())
        gaps.append(f"Mode labels disagree. {rendered}.")
    elif modes:
        evidence.append("Mode labels agree across the sections that declare them.")
    else:
        evidence.append("The pack uses a single mode line, or none.")
    if template_cited:
        evidence.append(f"{profile.drafting_relpath} points at {profile.template_filename}.")
    else:
        gaps.append(f"{profile.drafting_relpath} does not point at {profile.template_filename}.")

    if conflict or len(mode_sets) > 1:
        score = 3
    elif not template_cited:
        score = 4
    else:
        score = 5
    return _criterion("coherence", "Coherence", score, _coherence_requirement(profile), evidence, gaps)


def _coherence_requirement(profile: Profile) -> str:
    return (
        f"One procedure, one mode vocabulary, and a drafting step tied to the output template, "
        f"so an agent writing a {profile.skill_label} document does not invent the artifact."
    )


def _completeness(parsed: ParsedSkill, profile: Profile) -> CriterionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    haystack = parsed.pack_text.lower()
    for label, needle in profile.completeness:
        if needle in haystack:
            evidence.append(f"{label} is specified.")
        else:
            gaps.append(f"{label} is not specified.")
    soft: list[str] = []
    if "eval scenario" not in haystack and "references/eval-" not in haystack:
        soft.append("No eval scenario is in the pack, so the skill cannot be regression-tested from its own references.")
    required_missing = len(gaps)
    if required_missing == 0 and not soft:
        score = 5
    elif required_missing == 0:
        score = 4
    elif required_missing == 1:
        score = 3
    elif required_missing <= 3:
        score = 2
    else:
        score = 1
    gaps.extend(soft)
    requirement = (
        f"The pack specifies every field {profile.skill_label} must put in the document. "
        "A localized gap that does not drop a required field scores 4."
    )
    return _criterion("completeness", "Output completeness", score, requirement, evidence, gaps)


def _actionability(parsed: ParsedSkill, profile: Profile) -> CriterionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    if f"Running **/{parsed.name}**" in parsed.body:
        evidence.append("The announce line is exact.")
    else:
        gaps.append("The announce line does not name this skill.")
    if any(link.in_pack and link.exists and link.href.replace("\\", "/").startswith("subskills/") for link in parsed.links):
        evidence.append("The subskill table points at files that exist.")
    else:
        gaps.append("Subskill links do not resolve.")
    if parsed.section_prefix("mini example").strip():
        evidence.append("A mini example shows the happy path.")
    else:
        gaps.append("The mini example is missing.")
    if profile.output_path in parsed.pack_text:
        evidence.append(f"The happy path names {profile.output_path}.")
    else:
        gaps.append("The output path is not named.")
    if "explicit approval" in parsed.body.lower():
        evidence.append("The pack asks for explicit approval.")
    else:
        gaps.append("The pack does not ask for explicit approval.")

    score = _from_missing(len(gaps))
    unnamed = conflicting_procedures(parsed) or len({tuple(v) for v in mode_vocabularies(parsed).values()}) > 1
    template_missing = profile.template_filename not in parsed.file_text(profile.drafting_relpath)
    if score == 5 and (unnamed or template_missing):
        score = 4
        gaps.append("The happy path is executable, and an agent still has to choose a procedure or find the template.")
    requirement = "The happy path is executable: announce line, subskills, example, output path, and an approval question."
    return _criterion("actionability", "Actionability", score, requirement, evidence, gaps)


def _governance(parsed: ParsedSkill, profile: Profile) -> CriterionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    gate = parsed.section_prefix("approval gate").lower()
    if "not" in gate and "approval" in gate:
        evidence.append("Silence is not approval.")
    else:
        gaps.append("The approval gate does not say that silence is not approval.")
    if "explicit approval" in parsed.body.lower() and "draft" in parsed.body.lower():
        evidence.append("Drafts come before finals, and finals wait for approval.")
    else:
        gaps.append("Draft-before-finals is not stated.")
    if all(token in parsed.pack_text.lower() for token in ("low", "medium", "high", "regulated")):
        evidence.append("The risk-tier enum is present.")
    else:
        gaps.append("The risk-tier enum is incomplete.")
    from skill_evaluator.parse import contains_secret

    if not contains_secret(parsed.pack_text):
        evidence.append("Examples do not contain secret markers.")
    else:
        gaps.append("A secret-shaped token is present.")

    score = _from_missing(len(gaps))
    soft: list[str] = []
    if "untrusted" not in parsed.pack_text.lower():
        soft.append("Pasted tickets and notes are not marked as untrusted input.")
    deferred = parsed.pack_text.lower()
    has_owner = "owner" in deferred
    has_review = "review date" in deferred or "expiry" in deferred or "compensating" in deferred
    if has_owner and not has_review:
        soft.append("Deferred items require an owner and do not require a review date or compensating control.")
    if score >= 4 and soft:
        score = 4
        gaps.extend(soft)
    elif soft and score == 5:
        score = 4
        gaps.extend(soft)
    requirement = (
        f"Approval, risk tier, and stop rules are explicit for {profile.skill_label}, "
        "and skipped controls carry an owner plus a review date."
    )
    return _criterion("governance", "Governance", score, requirement, evidence, gaps)


def _fluency(parsed: ParsedSkill, profile: Profile) -> CriterionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    if parsed.line_count <= 500:
        evidence.append(f"SKILL.md is {parsed.line_count} lines, under the 500-line bar.")
    else:
        gaps.append(f"SKILL.md is {parsed.line_count} lines.")
    card = parsed.files.get("SKILL_CARD.md", "")
    expected = f"# SKILL_CARD — {parsed.name}"
    first = card.splitlines()[0].strip("\ufeff") if card else ""
    if first == expected:
        evidence.append("The skill card title matches the skill name.")
    elif not card:
        gaps.append("SKILL_CARD.md is missing.")
    else:
        gaps.append(f"The skill card title is {first!r}.")
    if parsed.has_h2_prefix("subskills") and parsed.has_h2_prefix("references"):
        evidence.append("Depth sits in subskills and references.")
    else:
        gaps.append("Subskills or references are not linked from the skill.")
    if parsed.line_count > 700 or len(parsed.h2()) < 4:
        score = 2
    elif not card or parsed.line_count > 500:
        score = 3
    elif gaps:
        score = 4
    else:
        score = 5
    requirement = f"The {profile.skill_label} pack is lean, scannable, and uses the canonical skill-card title."
    return _criterion("fluency", "Fluency and structure", score, requirement, evidence, gaps)
