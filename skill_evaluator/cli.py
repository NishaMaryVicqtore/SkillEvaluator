"""Command line entry for the skill evaluator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skill_evaluator.evaluate import evaluate
from skill_evaluator.report import to_json, to_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score a PRD or BRD skill file with G-Eval and JSON/Markdown schema parsing."
    )
    parser.add_argument("skill", help="Path to SKILL.md, or to the directory that contains it.")
    parser.add_argument("--profile", choices=("auto", "prd", "brd"), default="auto")
    parser.add_argument("--output", help="Write the Markdown report to this path.")
    parser.add_argument("--json", dest="json_path", help="Write the JSON report to this path.")
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Exit 1 when the combined score is below this threshold.",
    )
    args = parser.parse_args(argv)
    try:
        result = evaluate(args.skill, profile=args.profile)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    markdown = to_markdown(result)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown, encoding="utf-8")
    if args.json_path:
        payload = Path(args.json_path)
        payload.parent.mkdir(parents=True, exist_ok=True)
        payload.write_text(to_json(result), encoding="utf-8")
    _print_summary(result)
    if args.fail_under is not None and result.combined < args.fail_under:
        return 1
    return 0


def _print_summary(result) -> None:
    print(f"Skill: {result.parsed.name} ({result.profile.skill_label})")
    print(f"Combined: {result.combined:.2f} / 5 - {result.verdict}")
    print(f"G-Eval weighted: {result.geval_weighted:.2f} / 5")
    print(f"Schema: {result.schema_passed}/{result.schema_total} ({result.schema_scaled:.2f} / 5)")
    print("Aspects:")
    for aspect in result.aspects:
        print(
            f"  {aspect.label}: {aspect.combined:.2f} "
            f"(G-Eval {aspect.geval_score}, schema {aspect.schema_passed}/{aspect.schema_total})"
        )


if __name__ == "__main__":
    raise SystemExit(main())
