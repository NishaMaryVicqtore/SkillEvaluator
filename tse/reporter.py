from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from tse.models import GovernanceReport, OverallEvalReport


def _status_text(label: str, passed: bool) -> Text:
    return Text(label, style="bold green" if passed else "bold red")


def _overall_rationale(report: OverallEvalReport) -> str:
    if not report.tier1.passed:
        return "Tier 1 failed; later tiers were skipped."
    if report.tier2 is None or report.tier3 is None:
        return "Evaluation is incomplete."
    if report.tier2.status == "ERROR":
        return f"Tier 2 failed: {report.tier2.recommendation}"
    if report.tier2.status == "REJECTED_DUPLICATE":
        return (
            f"Tier 2 rejected the skill as a duplicate of "
            f"{report.tier2.closest_match}."
        )
    if report.tier2.status == "VERSION_UPDATE":
        baseline = report.tier2.previous_composite_score
        if baseline is not None and report.tier3.composite_score < baseline:
            return (
                f"Version update regressed from {baseline:.1f}% to "
                f"{report.tier3.composite_score:.1f}%."
            )
        if baseline is not None:
            return (
                f"Version update met the previous {baseline:.1f}% Tier 3 "
                f"baseline with {report.tier3.composite_score:.1f}%."
            )
    if not report.tier3.passed:
        return (
            f"Tier 3 did not meet both gates: composite "
            f"{report.tier3.composite_score:.1f}% (required 80.0%) and "
            f"uplift {report.tier3.uplift_score:+.1f} points "
            "(required +15.0)."
        )
    return "All required validation and benchmark gates passed."


def render_cli_scorecard(report: OverallEvalReport) -> None:
    """Render the complete TSE scorecard to the terminal."""
    console = Console()
    badge = (
        Text("[PASSED VERIFIED SKILL]", style="bold green")
        if report.overall_passed
        else Text("[FAILED]", style="bold red")
    )
    header = Text()
    header.append(f"Skill: {report.skill_id}\n", style="bold")
    header.append(f"Version: {report.skill_version}\n")
    header.append(f"Author: {report.author}\n")
    header.append_text(badge)
    console.print(Panel(header, title="Trimble Skill Evaluator", expand=False))

    table = Table(title="Validation and Benchmark Summary")
    table.add_column("Tier / Dimension", style="bold")
    table.add_column("Status")
    table.add_column("Result", justify="right")
    table.add_column("Details", overflow="fold")

    tier1_status = "PASSED" if report.tier1.passed else "FAILED"
    tier1_details = (
        "No violations"
        if not report.tier1.violations
        else "; ".join(report.tier1.violations)
    )
    table.add_row(
        "Tier 1 - Static & Security",
        _status_text(tier1_status, report.tier1.passed),
        f"{len(report.tier1.violations)} violation(s)",
        tier1_details,
    )

    if report.tier2 is None:
        table.add_row("Tier 2 - Deduplication", "SKIPPED", "-", "Tier 1 failed")
    else:
        tier2_styles = {
            "PASSED_UNIQUE": "bold green",
            "VERSION_UPDATE": "bold cyan",
            "WARNING_DISAMBIGUATE": "bold yellow",
            "REJECTED_DUPLICATE": "bold red",
            "ERROR": "bold red",
        }
        table.add_row(
            "Tier 2 - Deduplication",
            Text(
                report.tier2.status,
                style=tier2_styles.get(report.tier2.status, "bold red"),
            ),
            f"{report.tier2.max_similarity_score:.1%}",
            (
                f"{report.tier2.recommendation} "
                f"[backend: {report.tier2.similarity_backend}]"
            ),
        )

    if report.tier3 is None:
        table.add_row(
            "Tier 3 - Demo Sandbox",
            "SKIPPED",
            "-",
            "Not executed",
        )
    else:
        table.add_row(
            "Tier 3 - Composite",
            _status_text(
                "PASSED" if report.tier3.passed else "FAILED",
                report.tier3.passed,
            ),
            f"{report.tier3.composite_score:.1f}%",
            (
                f"Control: {report.tier3.control_composite_score:.1f}%, "
                f"Uplift: {report.tier3.uplift_score:+.1f} points, "
                f"Cases: {report.tier3.case_count}"
            ),
        )
        dimensions = (
            ("Correctness (35%)", report.tier3.correctness),
            ("Discoverability (25%)", report.tier3.discoverability),
            ("Efficiency (20%)", report.tier3.efficiency),
            ("Tool Reliability (10%)", report.tier3.tool_reliability),
            ("Safety (10%)", report.tier3.safety),
        )
        for label, score in dimensions:
            table.add_row(f"  {label}", "-", f"{score:.1f}%", "")

    console.print(table)
    console.print(Panel(_overall_rationale(report), title="Decision rationale"))


def render_governance_scorecard(report: GovernanceReport) -> None:
    """Render rule, skill, policy, eval, and architecture results."""
    console = Console()
    badge = (
        Text("[PASSED]", style="bold green")
        if report.passed
        else Text("[FAILED]", style="bold red")
    )
    header = Text()
    header.append(f"Governance: {report.governance_path}\n", style="bold")
    if report.cursor_path:
        header.append(f"Cursor rules: {report.cursor_path}\n")
    if report.project_path:
        header.append(f"Project: {report.project_path}\n")
    header.append_text(badge)
    console.print(Panel(header, title="TSE governance", expand=False))

    table = Table(title="Rules, skills, policies, evals, and architecture")
    table.add_column("Kind", style="bold")
    table.add_column("Asset")
    table.add_column("Status")
    table.add_column("Details", overflow="fold")
    labels = {
        "rule": "Rule",
        "skill": "Skill",
        "policy": "Policy",
        "eval": "Eval",
        "architecture": "Architecture skill",
    }
    for asset in report.assets:
        table.add_row(
            labels.get(asset.kind, asset.kind),
            asset.name,
            _status_text("PASSED" if asset.passed else "FAILED", asset.passed),
            "No violations" if asset.passed else "; ".join(asset.violations),
        )
    console.print(table)


def generate_governance_md(report: GovernanceReport) -> str:
    """Write a markdown report for a governance evaluation."""
    labels = {
        "rule": "Rule",
        "skill": "Skill",
        "policy": "Policy",
        "eval": "Eval",
        "architecture": "Architecture skill",
    }
    verdict = "PASSED" if report.passed else "FAILED"
    lines = [
        "# TSE governance report",
        "",
        f"- **Governance:** `{_md(report.governance_path)}`",
        f"- **Cursor rules:** `{_md(report.cursor_path or 'N/A')}`",
        f"- **Project:** `{_md(report.project_path or 'N/A')}`",
        f"- **Overall verdict:** **{verdict}**",
        "",
        "| Kind | Asset | Status | Details |",
        "| --- | --- | --- | --- |",
    ]
    for asset in report.assets:
        detail = "No violations" if asset.passed else "; ".join(asset.violations)
        lines.append(
            f"| {labels.get(asset.kind, asset.kind)} | {_md(asset.name)} | "
            f"{'PASSED' if asset.passed else 'FAILED'} | {_md(detail)} |"
        )
    lines.append("")
    return "\n".join(lines)


def _md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def generate_benchmark_md(
    report: OverallEvalReport,
    output_dir: Path,
) -> Path:
    """Write a BENCHMARK.md audit report in the evaluated skill directory."""
    generated_at = datetime.now(timezone.utc).isoformat()
    verdict = "PASSED VERIFIED SKILL" if report.overall_passed else "FAILED"
    lines = [
        "# TSE Benchmark Report",
        "",
        f"- **Skill ID:** `{_md(report.skill_id)}`",
        f"- **Version:** `{_md(report.skill_version)}`",
        f"- **Author:** {_md(report.author)}",
        f"- **Skill hash:** `{report.skill_hash}`",
        f"- **AGL-MANIFEST:** `{report.agl_manifest or 'N/A'}`",
        f"- **Generated:** {generated_at}",
        f"- **Overall verdict:** **{verdict}**",
        "",
        "## Decision rationale",
        "",
        _overall_rationale(report),
        "",
        "## Tier 1 — Static & Security",
        "",
        f"- **Status:** {'PASSED' if report.tier1.passed else 'FAILED'}",
        f"- **Violations:** {len(report.tier1.violations)}",
    ]

    if report.tier1.violations:
        lines.extend(
            ["", *[f"- {_md(violation)}" for violation in report.tier1.violations]]
        )

    lines.extend(["", "## Tier 2 — Catalog Deduplication", ""])
    if report.tier2 is None:
        lines.append("- **Status:** SKIPPED")
    else:
        lines.extend(
            [
                f"- **Status:** {report.tier2.status}",
                (
                    "- **Maximum similarity:** "
                    f"{report.tier2.max_similarity_score:.1%}"
                ),
                f"- **Closest match:** {_md(report.tier2.closest_match or 'N/A')}",
                f"- **Similarity backend:** {_md(report.tier2.similarity_backend)}",
                f"- **Recommendation:** {_md(report.tier2.recommendation)}",
            ]
        )
        if report.tier2.previous_version is not None:
            lines.append(
                f"- **Previous version:** {_md(report.tier2.previous_version)}"
            )
        if report.tier2.previous_composite_score is not None:
            lines.append(
                "- **Previous Tier 3 baseline:** "
                f"{report.tier2.previous_composite_score:.1f}%"
            )

    lines.extend(["", "## Tier 3 — Demo Sandbox", ""])
    if report.tier3 is None:
        lines.append("- **Status:** SKIPPED")
    else:
        lines.extend(
            [
                f"- **Status:** {'PASSED' if report.tier3.passed else 'FAILED'}",
                f"- **Cases:** {report.tier3.case_count}",
                (
                    "- **Control composite:** "
                    f"{report.tier3.control_composite_score:.1f}%"
                ),
                f"- **Composite score:** {report.tier3.composite_score:.1f}%",
                f"- **Uplift:** {report.tier3.uplift_score:+.1f} points",
                "",
                "| Dimension | Weight | Score |",
                "|---|---:|---:|",
                f"| Correctness | 35% | {report.tier3.correctness:.1f}% |",
                (
                    "| Discoverability | 25% | "
                    f"{report.tier3.discoverability:.1f}% |"
                ),
                f"| Efficiency | 20% | {report.tier3.efficiency:.1f}% |",
                (
                    "| Tool Reliability | 10% | "
                    f"{report.tier3.tool_reliability:.1f}% |"
                ),
                f"| Safety | 10% | {report.tier3.safety:.1f}% |",
                "",
                (
                    "Composite = 0.35(Correctness) + 0.25(Discoverability) + "
                    "0.20(Efficiency) + 0.10(Tool Reliability) + 0.10(Safety)."
                ),
                (
                    "Pass gates: treatment composite >= 80.0% and uplift "
                    ">= +15.0 percentage points."
                ),
                "",
                (
                    "> Demo-mode scores are deterministic simulations for the "
                    "hackathon prototype; they are not live model executions."
                ),
            ]
        )

    output_path = Path(output_dir) / "BENCHMARK.md"
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path
