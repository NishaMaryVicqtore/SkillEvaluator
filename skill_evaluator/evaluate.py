"""Run schema parsing and G-Eval, then combine them per aspect."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from skill_evaluator.geval import CriterionScore, score_criteria
from skill_evaluator.parse import ParsedSkill, parse_skill
from skill_evaluator.profiles import WEIGHTS, Profile, detect_profile
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


@dataclass
class Evaluation:
    skill_path: Path
    profile: Profile
    parsed: ParsedSkill
    assertions: list[Assertion]
    criteria: list[CriterionScore]
    schema_errors: list[str]
    evaluated_on: date

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
        labels = {item.id: item.criterion for item in self.criteria}
        scores = []
        for aspect_id, weight in WEIGHTS.items():
            related = [item for item in self.assertions if item.aspect == aspect_id]
            geval = next(item.score for item in self.criteria if item.id == aspect_id)
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

    @property
    def combined(self) -> float:
        return sum(aspect.combined * aspect.weight for aspect in self.aspects)

    @property
    def verdict(self) -> str:
        failed = [item.criterion for item in self.criteria if item.score < 3]
        if failed:
            return "Below the acceptable line. Failed dimensions: " + ", ".join(failed)
        if self.combined >= 4.5:
            return "Strong"
        if self.combined >= 4.0:
            return "Acceptable with documented gaps"
        return "Below the acceptable-with-gaps line"

    def external_links(self) -> list[str]:
        return [link.href for link in self.parsed.links if not link.in_pack]


def evaluate(skill: Path | str, profile: str = "auto", evaluated_on: date | None = None) -> Evaluation:
    parsed = parse_skill(Path(skill))
    selected = detect_profile(parsed.name, parsed.body, profile)
    assertions = build_assertions(parsed, selected)
    return Evaluation(
        skill_path=parsed.path,
        profile=selected,
        parsed=parsed,
        assertions=assertions,
        criteria=score_criteria(parsed, selected),
        schema_errors=validation_errors(assertions),
        evaluated_on=evaluated_on or date.today(),
    )
