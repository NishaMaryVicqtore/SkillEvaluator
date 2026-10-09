import hashlib
import json
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

from tse.models import OverallEvalReport
from tse.reporter import generate_benchmark_md, render_cli_scorecard
from tse.tier1_static import run_tier1_scan
from tse.tier2_dedup import run_tier2_dedup
from tse.tier3_sandbox import run_tier3_sandbox


app = typer.Typer()
console = Console()


def _skill_identity(skill_path: Path) -> tuple[str, str, str]:
    skill_id = skill_path.name
    version = "unknown"
    author = "unknown"
    metadata_path = skill_path / "metadata.yaml"
    try:
        metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return skill_id, version, author

    if isinstance(metadata, dict):
        skill_id = str(metadata.get("id") or skill_id)
        version = str(metadata.get("version") or version)
        author = str(metadata.get("author") or author)
    return skill_id, version, author


def _skill_hash(skill_path: Path) -> str:
    digest = hashlib.sha256()
    relative_paths = (
        Path("metadata.yaml"),
        Path("SKILL.md"),
        Path("tests/eval.json"),
    )
    for relative_path in relative_paths:
        path = skill_path / relative_path
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        digest.update(relative_path.as_posix().encode())
        digest.update(b"\0")
        digest.update(content.encode())
        digest.update(b"\0")
    return digest.hexdigest()


def _agl_manifest(skill_path: Path) -> str | None:
    for parent in (skill_path.resolve(), *skill_path.resolve().parents):
        manifest_path = parent / "behavior-manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        bundle_hash = manifest.get("bundleHash")
        return str(bundle_hash) if bundle_hash else None
    return None


def _overall_passed(report: OverallEvalReport) -> bool:
    if not report.tier1.passed or report.tier2 is None or report.tier3 is None:
        return False
    if report.tier2.status in {"ERROR", "REJECTED_DUPLICATE"}:
        return False
    if not report.tier3.passed:
        return False
    if report.tier2.status == "VERSION_UPDATE":
        baseline = report.tier2.previous_composite_score
        if baseline is not None:
            return report.tier3.composite_score >= baseline
    return True


@app.command()
def validate(
    skill_path: Path,
    demo: bool = typer.Option(True, "--demo/--no-demo"),
) -> None:
    """Run the complete TSE validation and benchmark pipeline."""
    if not demo:
        console.print(
            Text(
                "Live sandbox execution is not implemented; use --demo.",
                style="bold red",
            )
        )
        raise typer.Exit(code=2)

    skill_id, skill_version, author = _skill_identity(skill_path)
    tier2 = None
    tier3 = None

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        console=console,
    ) as progress:
        tier1_task = progress.add_task("Tier 1 - Static & Security", total=None)
        tier1 = run_tier1_scan(skill_path)
        progress.update(
            tier1_task,
            description=(
                "Tier 1 - PASSED" if tier1.passed else "Tier 1 - FAILED"
            ),
            completed=1,
            total=1,
        )

        if tier1.passed:
            tier2_task = progress.add_task(
                "Tier 2 - Catalog Deduplication",
                total=None,
            )
            tier2 = run_tier2_dedup(skill_path)
            progress.update(
                tier2_task,
                description=f"Tier 2 - {tier2.status}",
                completed=1,
                total=1,
            )

            tier3_task = progress.add_task("Tier 3 - Demo Sandbox", total=None)
            try:
                tier3 = run_tier3_sandbox(skill_path, demo=demo)
            except ValueError as exc:
                progress.update(
                    tier3_task,
                    description="Tier 3 - FAILED",
                    completed=1,
                    total=1,
                )
                console.print(Text(str(exc), style="bold red"))
            else:
                progress.update(
                    tier3_task,
                    description=(
                        "Tier 3 - PASSED" if tier3.passed else "Tier 3 - FAILED"
                    ),
                    completed=1,
                    total=1,
                )

    report = OverallEvalReport(
        skill_id=skill_id,
        skill_version=skill_version,
        author=author,
        skill_hash=_skill_hash(skill_path),
        agl_manifest=_agl_manifest(skill_path),
        overall_passed=False,
        tier1=tier1,
        tier2=tier2,
        tier3=tier3,
    )
    report.overall_passed = _overall_passed(report)
    render_cli_scorecard(report)

    if skill_path.is_dir():
        benchmark_path = generate_benchmark_md(report, skill_path)
        console.print(Text(f"Benchmark report: {benchmark_path}"))

    if not report.overall_passed:
        raise typer.Exit(code=1)


@app.command()
def scan(skill_path: Path) -> None:
    """Run Tier 1 static and security checks for a skill directory."""
    result = run_tier1_scan(skill_path)

    if result.passed:
        console.print(Text("PASSED - 0 violations", style="bold green"))
        return

    console.print(
        Text(
            f"FAILED - {len(result.violations)} violation(s)",
            style="bold red",
        )
    )
    for violation in result.violations:
        console.print(Text(f"  - {violation}"))
    raise typer.Exit(code=1)


@app.command()
def deduplicate(skill_path: Path) -> None:
    """Compare a skill with the offline mock registry."""
    result = run_tier2_dedup(skill_path)
    status_styles = {
        "REJECTED_DUPLICATE": "bold red",
        "WARNING_DISAMBIGUATE": "bold yellow",
        "PASSED_UNIQUE": "bold green",
        "VERSION_UPDATE": "bold cyan",
        "ERROR": "bold red",
    }

    console.print(
        Text(
            result.status,
            style=status_styles.get(result.status, "bold"),
        )
    )
    console.print(
        Text(f"Maximum similarity: {result.max_similarity_score:.1%}")
    )
    console.print(Text(f"Closest match: {result.closest_match or 'N/A'}"))
    console.print(Text(f"Similarity backend: {result.similarity_backend}"))
    console.print(Text(f"Recommendation: {result.recommendation}"))
    if result.status in {"ERROR", "REJECTED_DUPLICATE"}:
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Print the TSE prototype version."""
    typer.echo("Trimble Skill Evaluator v0.1.0-hackathon")
