"""Command line entry for the skill evaluator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skill_evaluator.evaluate import evaluate
from skill_evaluator.parse import parse_skill
from skill_evaluator.profiles import detect_profile
from skill_evaluator.report import to_json, to_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score a PRD, BRD, or architecture and design skill."
    )
    parser.add_argument("skill", nargs="?", help="Path to SKILL.md, or to the directory that contains it.")
    parser.add_argument("--profile", choices=("auto", "prd", "brd", "architect"), default="auto")
    parser.add_argument("--prd", help="Generated PRD markdown to score with a PRD skill.")
    parser.add_argument("--brd", help="Generated BRD markdown to score with a BRD skill.")
    parser.add_argument("--architect-skill", help="Architecture skill, when it is a different file from the design skill.")
    parser.add_argument("--design-skill", help="Design skill, when it is a different file from the architecture skill.")
    parser.add_argument("--architect-doc", help="Generated architecture document.")
    parser.add_argument("--design-doc", help="Generated design document.")
    parser.add_argument(
        "--design",
        help="One generated document that covers both architecture and design.",
    )
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
        skill, prd, brd, design_skill, design, architect_doc, design_doc = _resolve_inputs(args)
        result = evaluate(
            skill,
            profile=args.profile,
            prd=prd,
            brd=brd,
            design=design,
            design_skill=design_skill,
            architect_doc=architect_doc,
            design_doc=design_doc,
        )
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


def _resolve_inputs(args):
    skill = args.skill or args.architect_skill or args.design_skill
    if not skill:
        raise ValueError("Pass a skill file.")
    parsed = parse_skill(Path(skill))
    profile = detect_profile(parsed.name, parsed.body, args.profile)
    design_skill = args.design_skill
    if args.architect_skill and args.skill and _different(args.architect_skill, args.skill) and not design_skill:
        design_skill = args.skill
        skill = args.architect_skill
    elif args.architect_skill and not args.skill:
        skill = args.architect_skill
    if design_skill and not _different(design_skill, skill):
        design_skill = None
    prd = args.prd
    brd = args.brd
    design = args.design
    architect_doc = args.architect_doc
    design_doc = args.design_doc
    if profile.id in {"prd", "brd"}:
        if any(item for item in (design, design_skill, architect_doc, design_doc, args.architect_skill)):
            raise ValueError("Architecture and design files apply to an architecture skill.")
        document = prd or brd
        if document is None and _interactive():
            if _ask_prd_choice() == "document":
                document = _ask_file("Path to the generated PRD or BRD: ")
        if profile.id == "prd":
            prd = document
        else:
            brd = document
        return skill, prd, brd, None, None, None, None
    has_document = any(item for item in (design, architect_doc, design_doc))
    if not has_document and _interactive():
        if _ask_architect_choice() == "document":
            design, architect_doc, design_doc = _ask_architecture_documents()
    return skill, None, None, design_skill, design, architect_doc, design_doc


def _different(left: str, right: str) -> bool:
    return Path(left).resolve() != Path(right).resolve()


def _interactive() -> bool:
    return sys.stdin.isatty()


def _ask_prd_choice() -> str:
    print("What do you want to evaluate with G-Eval Framework (LLM-as-a-Judge) and JSON/Markdown Schema Parsing?")
    print("  1. PRD/BRD skill")
    print("  2. PRD/BRD skill along with the PRD/BRD document that was generated")
    return _choose({"1": "skill", "2": "document"})


def _ask_architect_choice() -> str:
    print(
        "What do you want to evaluate with G-Eval Framework (LLM-as-a-Judge), "
        "JSON/Markdown Schema Parsing and Topological Graph Validation?"
    )
    print("  1. Architect and Design skill")
    print("  2. Architect/Design skill along with the Architecture and design document that was generated")
    return _choose({"1": "skill", "2": "document"})


def _choose(answers: dict[str, str]) -> str:
    while True:
        choice = input("Choice [1/2]: ").strip().lower()
        if choice in answers:
            return answers[choice]
        print("Enter 1 or 2.")


def _ask_file(prompt: str) -> str:
    while True:
        entered = input(prompt).strip().strip('"')
        if entered and Path(entered).is_file():
            return entered
        print("That file was not found.")


def _ask_architecture_documents() -> tuple[str | None, str | None, str | None]:
    print("If the architecture document and the design document are different files, enter both paths.")
    while True:
        architecture = input("Architecture document path (press Enter when one file covers both): ").strip().strip('"')
        design = input("Design document path: ").strip().strip('"')
        if architecture and not Path(architecture).is_file():
            print("The architecture document was not found.")
            continue
        if design and not Path(design).is_file():
            print("The design document was not found.")
            continue
        if architecture and design:
            return None, architecture, design
        if design or architecture:
            return design or architecture, None, None
        print("Enter at least one document path.")


def _print_summary(result) -> None:
    print(f"Skill: {result.parsed.name} ({result.profile.skill_label})")
    if result.subjects:
        for subject in result.subjects:
            print(f"{subject.role}: {subject.score:.2f} / 5")
            for algorithm in subject.algorithms:
                print(f"  {algorithm.label}: {algorithm.score:.2f} / 5")
                for item in algorithm.criteria:
                    print(f"    {item.criterion}: {item.score}")
        print(f"Combined: {result.combined:.2f} / 5 - {result.verdict}")
        return
    if result.artifact is not None:
        print(f"Skill pack: {result.skill_combined:.2f} / 5")
        kind = "BRD" if result.profile.id == "brd" else "PRD"
        print(f"Generated {kind}: {result.artifact_combined:.2f} / 5")
    print(f"Combined: {result.combined:.2f} / 5 - {result.verdict}")
    print(f"G-Eval weighted: {result.geval_weighted:.2f} / 5")
    print(f"Schema: {result.schema_passed}/{result.schema_total} ({result.schema_scaled:.2f} / 5)")
    print("Skill aspects:")
    for aspect in result.aspects:
        print(
            f"  {aspect.label}: {aspect.combined:.2f} "
            f"(G-Eval {aspect.geval_score}, schema {aspect.schema_passed}/{aspect.schema_total})"
        )
    if result.artifact is not None:
        print(f"{'BRD' if result.profile.id == 'brd' else 'PRD'} aspects:")
        for aspect in result.artifact_aspects:
            print(
                f"  {aspect.label}: {aspect.combined:.2f} "
                f"(G-Eval {aspect.geval_score}, schema {aspect.schema_passed}/{aspect.schema_total})"
            )


if __name__ == "__main__":
    raise SystemExit(main())
