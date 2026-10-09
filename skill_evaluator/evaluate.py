"""Run schema parsing and G-Eval, then combine them per aspect."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from skill_evaluator.architect_eval import AlgorithmScore, score_architect_design, score_architect_skill
from skill_evaluator.geval import CriterionScore, score_criteria
from skill_evaluator.governance_eval import score_governance
from skill_evaluator.parse import ParsedSkill, parse_skill
from skill_evaluator.prd_outcome import PRD_WEIGHTS, ArtifactResult, score_brd, score_prd
from skill_evaluator.profiles import GOVERNANCE, WEIGHTS, Profile, detect_profile
from skill_evaluator.schema_checks import Assertion, build_assertions, validation_errors

SCHEMA_BLEND = 0.4
GEVAL_BLEND = 0.6


@dataclass(frozen=True)
class AspectScore:
    id: str
    label: str
    weight: float
    geval_score: int
    schema_passed: int
    schema_total: int

    @property
    def schema_scaled(self) -> float:
        if self.schema_total == 0:
            return 5.0
        return (self.schema_passed / self.schema_total) * 5

    @property
    def combined(self) -> float:
        return SCHEMA_BLEND * self.schema_scaled + GEVAL_BLEND * self.geval_score


@dataclass(frozen=True)
class ScoredSubject:
    role: str
    path: str
    algorithms: tuple[AlgorithmScore, ...]

    @property
    def score(self) -> float:
        if not self.algorithms:
            return 0.0
        return sum(item.score for item in self.algorithms) / len(self.algorithms)


@dataclass
class Evaluation:
    skill_path: Path
    profile: Profile
    parsed: ParsedSkill
    assertions: list[Assertion]
    criteria: list[CriterionScore]
    schema_errors: list[str]
    evaluated_on: date
    artifact: ArtifactResult | None = None
    algorithms: tuple[AlgorithmScore, ...] | None = None
    design_algorithms: tuple[AlgorithmScore, ...] | None = None
    design_path: str | None = None
    target: str | None = None
    subjects: tuple[ScoredSubject, ...] = ()

    @property
    def schema_passed(self) -> int:
        return sum(1 for item in self.assertions if item.passed)

    @property
    def schema_total(self) -> int:
        return len(self.assertions)

    @property
    def schema_ratio(self) -> float:
        if not self.schema_total:
            return 0.0
        return self.schema_passed / self.schema_total

    @property
    def schema_scaled(self) -> float:
        return self.schema_ratio * 5

    @property
    def geval_mean(self) -> float:
        if not self.criteria:
            return 0.0
        return sum(item.score for item in self.criteria) / len(self.criteria)

    @property
    def geval_weighted(self) -> float:
        return sum(item.score * item.weight for item in self.criteria)

    @property
    def aspects(self) -> list[AspectScore]:
        if self.target in {"architecture", "design", "both"} or self.algorithms:
            return []
        return build_aspects(self.assertions, self.criteria, WEIGHTS)

    @property
    def skill_combined(self) -> float:
        if self.algorithms:
            return _mean_algorithms(self.algorithms)
        if self.target:
            return 0.0
        return sum(aspect.combined * aspect.weight for aspect in self.aspects)

    @property
    def artifact_aspects(self) -> list[AspectScore]:
        if self.artifact is None:
            return []
        return build_aspects(self.artifact.assertions, self.artifact.criteria, PRD_WEIGHTS)

    @property
    def artifact_combined(self) -> float:
        return sum(aspect.combined * aspect.weight for aspect in self.artifact_aspects)

    @property
    def artifact_schema_passed(self) -> int:
        if self.artifact is None:
            return 0
        return sum(1 for item in self.artifact.assertions if item.passed)

    @property
    def artifact_schema_total(self) -> int:
        if self.artifact is None:
            return 0
        return len(self.artifact.assertions)

    @property
    def design_combined(self) -> float:
        if not self.design_algorithms:
            return 0.0
        return _mean_algorithms(self.design_algorithms)

    @property
    def combined(self) -> float:
        if self.subjects:
            return sum(item.score for item in self.subjects) / len(self.subjects)
        if self.target == "design":
            return self.design_combined
        if self.target == "both":
            return (self.skill_combined + self.design_combined) / 2
        if self.algorithms:
            if self.design_algorithms:
                return (self.skill_combined + self.design_combined) / 2
            return self.skill_combined
        if self.artifact is None:
            return self.skill_combined
        return (self.skill_combined + self.artifact_combined) / 2

    @property
    def verdict(self) -> str:
        if self.subjects:
            failed: list[str] = []
            for subject in self.subjects:
                for algorithm in subject.algorithms:
                    if algorithm.score < 3:
                        failed.append(algorithm.label)
                    failed.extend(item.criterion for item in algorithm.criteria if item.score < 3)
            if failed:
                names = list(dict.fromkeys(failed))
                return "Below the acceptable line. Failed dimensions: " + ", ".join(names)
            return verdict_for([], self.combined)
        if self.target == "design" and self.design_algorithms:
            groups = [self.design_algorithms]
        elif self.target == "architecture" and self.algorithms:
            groups = [self.algorithms]
        elif self.algorithms:
            groups = [self.algorithms]
            if self.design_algorithms:
                groups.append(self.design_algorithms)
        else:
            groups = []
        if groups:
            failed: list[str] = []
            for group in groups:
                for algorithm in group:
                    if algorithm.score < 3:
                        failed.append(algorithm.label)
                    failed.extend(item.criterion for item in algorithm.criteria if item.score < 3)
            if failed:
                names = list(dict.fromkeys(failed))
                return "Below the acceptable line. Failed dimensions: " + ", ".join(names)
            return verdict_for([], self.combined)
        if self.artifact is None:
            return verdict_for(self.criteria, self.skill_combined)
        return verdict_for(self.artifact.criteria, self.combined)

    def external_links(self) -> list[str]:
        return [link.href for link in self.parsed.links if not link.in_pack]


def _architect_subjects(
    parsed: ParsedSkill,
    design_skill: Path | str | None,
    design: Path | str | None,
    architect_doc: Path | str | None,
    design_doc: Path | str | None,
) -> tuple[ScoredSubject, ...]:
    subjects: list[ScoredSubject] = []
    primary_role = "Architecture skill" if design_skill else "Architect and design skill"
    subjects.append(ScoredSubject(primary_role, str(parsed.path), score_architect_skill(parsed)))
    if design_skill is not None:
        other = parse_skill(Path(design_skill))
        if other.path.resolve() == parsed.path.resolve():
            raise ValueError("The design skill is the same file as the architecture skill. Pass it once.")
        subjects.append(ScoredSubject("Design skill", str(other.path), score_architect_skill(other)))
    documents = _document_inputs(design, architect_doc, design_doc)
    for role, path in documents:
        subjects.append(ScoredSubject(role, str(Path(path).resolve()), score_architect_design(Path(path))))
    return tuple(subjects)


def _document_inputs(
    design: Path | str | None,
    architect_doc: Path | str | None,
    design_doc: Path | str | None,
) -> list[tuple[str, Path | str]]:
    if architect_doc and design_doc and Path(architect_doc).resolve() != Path(design_doc).resolve():
        documents = [("Architecture document", architect_doc), ("Design document", design_doc)]
        if design and Path(design).resolve() not in {Path(architect_doc).resolve(), Path(design_doc).resolve()}:
            documents.append(("Architecture and design document", design))
        return documents
    single = design or architect_doc or design_doc
    if single is None:
        return []
    if architect_doc and not design and not design_doc:
        return [("Architecture document", architect_doc)]
    if design_doc and not design and not architect_doc:
        return [("Design document", design_doc)]
    return [("Architecture and design document", single)]


def _mean_algorithms(algorithms: tuple[AlgorithmScore, ...]) -> float:
    if not algorithms:
        return 0.0
    return sum(item.score for item in algorithms) / len(algorithms)


def build_aspects(
    assertions: list[Assertion],
    criteria: list[CriterionScore],
    weights: dict[str, float],
) -> list[AspectScore]:
    labels = {item.id: item.criterion for item in criteria}
    scores = []
    for aspect_id, weight in weights.items():
        related = [item for item in assertions if item.aspect == aspect_id]
        geval = next(item.score for item in criteria if item.id == aspect_id)
        scores.append(
            AspectScore(
                id=aspect_id,
                label=labels[aspect_id],
                weight=weight,
                geval_score=geval,
                schema_passed=sum(1 for item in related if item.passed),
                schema_total=len(related),
            )
        )
    return scores


def verdict_for(criteria: list[CriterionScore], score: float) -> str:
    failed = [item.criterion for item in criteria if item.score < 3]
    if failed:
        return "Below the acceptable line. Failed dimensions: " + ", ".join(failed)
    if score >= 4.5:
        return "Strong"
    if score >= 4.0:
        return "Acceptable with documented gaps"
    return "Below the acceptable-with-gaps line"


def evaluate_governance(
    governance: Path | str,
    cursor: Path | str | None = None,
    project: Path | str | None = None,
    evaluated_on: date | None = None,
) -> Evaluation:
    """Score rules, skills, policies, evals, and architecture skills with the three algorithms."""
    rows = score_governance(Path(governance), Path(cursor) if cursor else None, Path(project) if project else None)
    if not rows:
        raise ValueError("No rules, skills, policies, evals, or architecture skills were found.")
    subjects = tuple(ScoredSubject(row.role, row.path, row.algorithms) for row in rows)
    skill_path = next((Path(row.path) for row in rows if row.role.startswith("Skill —")), Path(rows[0].path))
    parsed = parse_skill(skill_path)
    schema_groups = [algorithm.checks for row in rows for algorithm in row.algorithms if algorithm.id == "schema"]
    schema_checks = [check for group in schema_groups for check in group]
    schema_errors = [message for group in schema_groups for message in validation_errors(list(group))]
    geval = next(algorithm for algorithm in rows[0].algorithms if algorithm.id == "geval")
    return Evaluation(
        skill_path=parsed.path,
        profile=GOVERNANCE,
        parsed=parsed,
        assertions=schema_checks,
        criteria=list(geval.criteria),
        schema_errors=schema_errors,
        evaluated_on=evaluated_on or date.today(),
        algorithms=subjects[0].algorithms,
        target="governance",
        subjects=subjects,
    )


def evaluate(
    skill: Path | str,
    profile: str = "auto",
    evaluated_on: date | None = None,
    prd: Path | str | None = None,
    design: Path | str | None = None,
    target: str | None = None,
    design_skill: Path | str | None = None,
    architect_doc: Path | str | None = None,
    design_doc: Path | str | None = None,
    brd: Path | str | None = None,
) -> Evaluation:
    del target
    if prd is not None and brd is not None:
        raise ValueError("Pass either a generated PRD or a generated BRD, not both.")
    if prd is not None and any(item is not None for item in (design, architect_doc, design_doc, design_skill)):
        raise ValueError("Pass either a generated PRD or architecture inputs, not both.")
    if brd is not None and any(item is not None for item in (design, architect_doc, design_doc, design_skill)):
        raise ValueError("Pass either a generated BRD or architecture inputs, not both.")
    parsed = parse_skill(Path(skill))
    selected = detect_profile(parsed.name, parsed.body, profile)
    if selected.id == "architect":
        if prd is not None or brd is not None:
            raise ValueError("An architecture skill takes architecture and design files, not a PRD or BRD.")
        subjects = _architect_subjects(parsed, design_skill, design, architect_doc, design_doc)
        documents = tuple(item for item in subjects if item.role.endswith("document"))
        schema_algorithm = next(item for item in subjects[0].algorithms if item.id == "schema")
        geval_algorithm = next(item for item in subjects[0].algorithms if item.id == "geval")
        return Evaluation(
            skill_path=parsed.path,
            profile=selected,
            parsed=parsed,
            assertions=list(schema_algorithm.checks),
            criteria=list(geval_algorithm.criteria),
            schema_errors=validation_errors(list(schema_algorithm.checks)),
            evaluated_on=evaluated_on or date.today(),
            algorithms=subjects[0].algorithms,
            design_algorithms=documents[0].algorithms if documents else None,
            design_path=documents[0].path if documents else None,
            target="skill+document" if documents else "skill",
            subjects=subjects,
        )
    if any(item is not None for item in (design, design_skill, architect_doc, design_doc)):
        raise ValueError(
            "Architecture and design files can only be scored with an architecture skill. "
            f"This pack resolved to {selected.skill_label}."
        )
    assertions = build_assertions(parsed, selected)
    artifact = None
    if prd is not None:
        if selected.id != "prd":
            raise ValueError(
                "A generated PRD can only be scored with a PRD skill. "
                f"This pack resolved to {selected.skill_label}."
            )
        artifact = score_prd(parsed, selected, Path(prd))
    if brd is not None:
        if selected.id != "brd":
            raise ValueError(
                "A generated BRD can only be scored with a BRD skill. "
                f"This pack resolved to {selected.skill_label}."
            )
        artifact = score_brd(parsed, selected, Path(brd))
    return Evaluation(
        skill_path=parsed.path,
        profile=selected,
        parsed=parsed,
        assertions=assertions,
        criteria=score_criteria(parsed, selected),
        schema_errors=validation_errors(assertions),
        evaluated_on=evaluated_on or date.today(),
        artifact=artifact,
    )
