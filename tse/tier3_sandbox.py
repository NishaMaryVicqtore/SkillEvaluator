import json
from pathlib import Path
from statistics import fmean
from typing import Any

from pydantic import ValidationError

from tse.models import TestCase, Tier3Result


DIMENSION_WEIGHTS = {
    "correctness": 0.35,
    "discoverability": 0.25,
    "efficiency": 0.20,
    "tool_reliability": 0.10,
    "safety": 0.10,
}

TRIGGER_CATEGORIES = {"direct_trigger", "paraphrased_trigger"}

DEFAULT_DEMO_METRICS = {
    "direct_trigger": {
        "control": {
            "correctness": 45.0,
            "triggered": False,
            "tokens": 1800,
            "latency_ms": 3200,
            "tool_reliability": 45.0,
            "safety": 100.0,
        },
        "treatment": {
            "correctness": 98.0,
            "triggered": True,
            "tokens": 700,
            "latency_ms": 1200,
            "tool_reliability": 98.0,
            "safety": 100.0,
        },
    },
    "paraphrased_trigger": {
        "control": {
            "correctness": 35.0,
            "triggered": False,
            "tokens": 2200,
            "latency_ms": 3800,
            "tool_reliability": 30.0,
            "safety": 100.0,
        },
        "treatment": {
            "correctness": 94.0,
            "triggered": True,
            "tokens": 850,
            "latency_ms": 1500,
            "tool_reliability": 94.0,
            "safety": 100.0,
        },
    },
    "hard_distractor": {
        "control": {
            "correctness": 90.0,
            "triggered": False,
            "tokens": 700,
            "latency_ms": 900,
            "tool_reliability": 100.0,
            "safety": 100.0,
        },
        "treatment": {
            "correctness": 96.0,
            "triggered": False,
            "tokens": 250,
            "latency_ms": 350,
            "tool_reliability": 100.0,
            "safety": 97.0,
        },
    },
    "soft_distractor": {
        "control": {
            "correctness": 100.0,
            "triggered": False,
            "tokens": 500,
            "latency_ms": 700,
            "tool_reliability": 100.0,
            "safety": 100.0,
        },
        "treatment": {
            "correctness": 100.0,
            "triggered": False,
            "tokens": 150,
            "latency_ms": 250,
            "tool_reliability": 100.0,
            "safety": 100.0,
        },
    },
}


def _load_test_cases(eval_path: Path) -> list[TestCase]:
    try:
        payload = json.loads(eval_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Evaluation fixture is missing: {eval_path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load evaluation fixture: {exc}") from exc

    raw_cases = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("tests/eval.json must contain at least one test case")

    try:
        return [TestCase.model_validate(case) for case in raw_cases]
    except ValidationError as exc:
        raise ValueError(f"Invalid test case: {exc}") from exc


def _default_metrics(category: str, arm: str) -> dict[str, Any]:
    category_metrics = DEFAULT_DEMO_METRICS.get(category)
    if category_metrics is not None:
        return dict(category_metrics[arm])
    return {
        "correctness": 75.0,
        "triggered": category in TRIGGER_CATEGORIES,
        "tokens": 1200 if arm == "control" else 700,
        "latency_ms": 1800 if arm == "control" else 1000,
        "tool_reliability": 85.0,
        "safety": 90.0,
    }


def _case_metrics(case: TestCase, arm: str) -> dict[str, Any]:
    metrics = _default_metrics(case.category, arm)
    overrides = case.expected_behavior.get(f"demo_{arm}", {})
    if isinstance(overrides, dict):
        metrics.update(overrides)
    return metrics


def _score(value: Any, label: str) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not 0.0 <= score <= 100.0:
        raise ValueError(f"{label} must be between 0 and 100")
    return score


def _positive_number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if number <= 0:
        raise ValueError(f"{label} must be greater than zero")
    return number


def _discoverability_score(
    cases: list[TestCase],
    arm_metrics: list[dict[str, Any]],
) -> float:
    trigger_results: list[float] = []
    distractor_results: list[float] = []
    for case, metrics in zip(cases, arm_metrics, strict=True):
        should_trigger = bool(
            case.expected_behavior.get(
                "should_trigger",
                case.category in TRIGGER_CATEGORIES,
            )
        )
        did_trigger = bool(metrics["triggered"])
        result = 100.0 if did_trigger == should_trigger else 0.0
        if should_trigger:
            trigger_results.append(result)
        else:
            distractor_results.append(result)

    components = []
    if trigger_results:
        components.append(fmean(trigger_results))
    if distractor_results:
        components.append(fmean(distractor_results))
    return fmean(components)


def _efficiency_score(
    control_metrics: list[dict[str, Any]],
    treatment_metrics: list[dict[str, Any]],
) -> float:
    control_tokens = 0
    control_latency = 0
    treatment_tokens = 0
    treatment_latency = 0

    for index, (control, treatment) in enumerate(
        zip(control_metrics, treatment_metrics, strict=True)
    ):
        control_tokens += _positive_number(
            control["tokens"],
            f"case {index} control tokens",
        )
        control_latency += _positive_number(
            control["latency_ms"],
            f"case {index} control latency_ms",
        )
        treatment_tokens += _positive_number(
            treatment["tokens"],
            f"case {index} treatment tokens",
        )
        treatment_latency += _positive_number(
            treatment["latency_ms"],
            f"case {index} treatment latency_ms",
        )

    token_reduction = 100.0 * (control_tokens - treatment_tokens) / control_tokens
    latency_reduction = (
        100.0 * (control_latency - treatment_latency) / control_latency
    )
    return max(0.0, min(100.0, fmean((token_reduction, latency_reduction))))


def _arm_dimensions(
    cases: list[TestCase],
    arm_metrics: list[dict[str, Any]],
) -> tuple[float, float, float, float]:
    correctness = fmean(
        _score(metrics["correctness"], "correctness")
        for metrics in arm_metrics
    )
    discoverability = _discoverability_score(cases, arm_metrics)
    trigger_metrics = [
        metrics
        for case, metrics in zip(cases, arm_metrics, strict=True)
        if bool(
            case.expected_behavior.get(
                "should_trigger",
                case.category in TRIGGER_CATEGORIES,
            )
        )
    ]
    tool_reliability = (
        fmean(
            _score(metrics["tool_reliability"], "tool_reliability")
            for metrics in trigger_metrics
        )
        if trigger_metrics
        else 100.0
    )
    safety = fmean(
        _score(metrics["safety"], "safety") for metrics in arm_metrics
    )
    return correctness, discoverability, tool_reliability, safety


def _composite(
    correctness: float,
    discoverability: float,
    efficiency: float,
    tool_reliability: float,
    safety: float,
) -> float:
    return (
        DIMENSION_WEIGHTS["correctness"] * correctness
        + DIMENSION_WEIGHTS["discoverability"] * discoverability
        + DIMENSION_WEIGHTS["efficiency"] * efficiency
        + DIMENSION_WEIGHTS["tool_reliability"] * tool_reliability
        + DIMENSION_WEIGHTS["safety"] * safety
    )


def run_tier3_sandbox(skill_dir: Path, demo: bool = True) -> Tier3Result:
    """Run the deterministic Tier 3 demo simulation."""
    if not demo:
        raise ValueError("Live sandbox execution is not implemented; use --demo.")

    cases = _load_test_cases(Path(skill_dir) / "tests" / "eval.json")
    control_metrics = [_case_metrics(case, "control") for case in cases]
    treatment_metrics = [_case_metrics(case, "treatment") for case in cases]
    (
        control_correctness,
        control_discoverability,
        control_tool_reliability,
        control_safety,
    ) = _arm_dimensions(cases, control_metrics)
    (
        correctness,
        discoverability,
        tool_reliability,
        safety,
    ) = _arm_dimensions(cases, treatment_metrics)
    efficiency = _efficiency_score(control_metrics, treatment_metrics)

    control_composite = _composite(
        control_correctness,
        control_discoverability,
        0.0,
        control_tool_reliability,
        control_safety,
    )
    composite_score = _composite(
        correctness,
        discoverability,
        efficiency,
        tool_reliability,
        safety,
    )
    uplift_score = composite_score - control_composite

    return Tier3Result(
        composite_score=round(composite_score, 2),
        control_composite_score=round(control_composite, 2),
        uplift_score=round(uplift_score, 2),
        correctness=round(correctness, 2),
        discoverability=round(discoverability, 2),
        efficiency=round(efficiency, 2),
        tool_reliability=round(tool_reliability, 2),
        safety=round(safety, 2),
        case_count=len(cases),
        passed=composite_score >= 80.0 and uplift_score >= 15.0,
    )
