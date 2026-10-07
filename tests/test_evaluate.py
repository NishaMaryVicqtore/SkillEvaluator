from pathlib import Path

import pytest

from skill_evaluator.cli import main
from skill_evaluator.evaluate import evaluate
from skill_evaluator.prd_outcome import PRD_WEIGHTS
from skill_evaluator.profiles import WEIGHTS

ROOT = Path(__file__).resolve().parents[1]
GOOD = ROOT / "tests" / "fixtures" / "good_prd" / "SKILL.md"
GAP = ROOT / "tests" / "fixtures" / "gap_brd" / "SKILL.md"
GENERATED = ROOT / "tests" / "fixtures" / "generated" / "good_prd.md"
THIN = ROOT / "tests" / "fixtures" / "generated" / "thin_prd.md"
REAL_PRD = Path(r"C:\Users\nvicqto\.cursor\skills\prd\SKILL.md")
REAL_BRD = Path(r"C:\Users\nvicqto\.cursor\skills\brd\SKILL.md")


def _by_id(result):
    return {item.id: item for item in result.assertions}


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1) < 1e-9
    assert abs(sum(PRD_WEIGHTS.values()) - 1) < 1e-9


def test_good_prd_pack_is_valid_and_strong():
    result = evaluate(GOOD)
    assert result.profile.id == "prd"
    assert result.schema_errors == []
    assert result.schema_passed == result.schema_total
    assert all(item.score == 5 for item in result.criteria)
    assert result.combined == 5
    assert result.verdict == "Strong"


def test_gap_brd_reports_each_failed_aspect():
    result = evaluate(GAP)
    checks = _by_id(result)
    assert result.profile.id == "brd"
    assert checks["skill_card_title"].passed is False
    assert checks["done_when_evidence"].passed is False
    assert checks["single_procedure"].passed is False
    assert checks["one_mode_vocabulary"].passed is False
    assert checks["drafting_cites_template"].passed is False
    assert any("True was expected" in message for message in result.schema_errors)
    scores = {item.id: item.score for item in result.criteria}
    assert scores["coherence"] == 3
    assert scores["completeness"] == 4
    assert scores["governance"] == 4
    assert result.combined < evaluate(GOOD).combined
    assert abs(result.combined - sum(aspect.combined * aspect.weight for aspect in result.aspects)) < 1e-9


def test_cli_writes_reports(tmp_path: Path):
    markdown = tmp_path / "report.md"
    payload = tmp_path / "report.json"
    exit_code = main([str(GOOD), "--output", str(markdown), "--json", str(payload), "--fail-under", "4.5"])
    assert exit_code == 0
    assert "Combined score" in markdown.read_text(encoding="utf-8")
    assert '"combined": 5' in payload.read_text(encoding="utf-8") or '"combined": 5.0' in payload.read_text(encoding="utf-8")


def test_skill_and_generated_prd_score_together():
    result = evaluate(GOOD, prd=GENERATED)
    assert result.artifact is not None
    assert result.skill_combined == 5
    assert result.artifact.schema_errors == []
    assert all(item.score == 5 for item in result.artifact.criteria)
    assert result.artifact_combined == 5
    assert result.combined == 5
    assert result.verdict == "Strong"


def test_thin_prd_scores_below_the_skill():
    result = evaluate(GOOD, prd=THIN)
    assert result.skill_combined == 5
    assert result.artifact_combined < 4
    assert result.combined < result.skill_combined
    assert result.combined == (result.skill_combined + result.artifact_combined) / 2
    checks = {item.id: item for item in result.artifact.assertions}
    assert checks["risk_tier_selected"].passed is False
    assert checks["unique_requirement_ids"].passed is False
    assert checks["heading_problem_statement"].passed is False
    assert any("True was expected" in message for message in result.artifact.schema_errors)
    assert result.verdict.startswith("Below the acceptable line")


def test_prd_input_requires_a_prd_skill():
    with pytest.raises(ValueError, match="PRD skill"):
        evaluate(GAP, prd=GENERATED)


def test_cli_scores_skill_and_prd(tmp_path: Path):
    markdown = tmp_path / "report.md"
    payload = tmp_path / "report.json"
    exit_code = main(
        [str(GOOD), "--prd", str(GENERATED), "--output", str(markdown), "--json", str(payload), "--fail-under", "4.5"]
    )
    assert exit_code == 0
    text = markdown.read_text(encoding="utf-8")
    assert "Generated PRD" in text
    assert "Skill pack" in text
    body = payload.read_text(encoding="utf-8")
    assert '"mode": "skill+prd"' in body
    refused = main([str(GAP), "--prd", str(GENERATED)])
    assert refused == 2


def test_real_prd_and_brd_skills_score_each_aspect():
    if not REAL_PRD.is_file() or not REAL_BRD.is_file():
        return
    prd = evaluate(REAL_PRD)
    brd = evaluate(REAL_BRD)
    assert prd.profile.id == "prd"
    assert brd.profile.id == "brd"
    assert {item.id for item in prd.criteria} == set(WEIGHTS)
    prd_checks = _by_id(prd)
    brd_checks = _by_id(brd)
    assert prd_checks["drafting_cites_template"].passed is True
    assert prd_checks["skill_card_title"].passed is False
    assert prd_checks["done_when_evidence"].passed is False
    assert prd_checks["single_procedure"].passed is False
    assert next(item.score for item in prd.criteria if item.id == "coherence") == 3
    assert brd_checks["drafting_cites_template"].passed is False
    assert brd_checks["skill_card_title"].passed is False
    assert next(item.score for item in brd.criteria if item.id == "coherence") == 4
    assert all(1 <= item.score <= 5 for item in prd.criteria + brd.criteria)
    assert any("True was expected" in message for message in prd.schema_errors)


def test_prd_prompt_keeps_the_skill_report(monkeypatch, tmp_path: Path, capsys):
    monkeypatch.setattr("skill_evaluator.cli._interactive", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "1")
    report = tmp_path / "skill.md"
    assert main([str(GOOD), "--output", str(report)]) == 0
    assert "JSON/Markdown Schema Parsing" in capsys.readouterr().out
    text = report.read_text(encoding="utf-8")
    assert text.startswith("# Skill evaluation — /prd")
    assert "## Generated PRD" not in text
    assert "| Aspect | Weight | G-Eval | Schema | Aspect score |" in text


def test_prd_prompt_scores_the_generated_document(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("skill_evaluator.cli._interactive", lambda: True)
    answers = iter(["2", str(GENERATED)])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    report = tmp_path / "both.md"
    assert main([str(GOOD), "--output", str(report)]) == 0
    text = report.read_text(encoding="utf-8")
    assert "# Skill and generated PRD evaluation — /prd" in text
    assert "## Generated PRD" in text
    assert "### PRD G-Eval" in text


def test_brd_document_uses_the_same_report_shape(tmp_path: Path):
    document = tmp_path / "BRD.md"
    document.write_text(
        "\n".join(
            [
                "# BRD",
                "## Overview",
                "The billing export gives finance a daily file.",
                "## Business objectives",
                "Finance receives the daily export before 06:00.",
                "## Scope and boundaries",
                "In scope: daily export. Out of scope: invoicing.",
                "## Stakeholders and RACI",
                "Finance is accountable. Engineering is responsible. Audit is consulted. Support is informed.",
                "## Business workflows",
                "The export runs after close.",
                "## Happy paths",
                "The job must write the file when the ledger closes.",
                "## Alternate paths",
                "The job must retry when the ledger is late.",
                "## Exception paths",
                "The job must alert finance when the file cannot be written.",
                "## Operational paths",
                "Support must see the last successful run date.",
                "## Business rules",
                "A closed ledger must not be exported twice.",
                "## Compliance, audit, and retention",
                "The file is retained for seven years.",
                "## Traceability to PRD",
                "This BRD traces to the approved PRD and REQ-1.",
                "## Approval record",
                "Status: Approved. Date: 2026-10-05. Risk tier: medium.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result = evaluate(GAP, brd=document)
    assert result.artifact is not None
    assert [item.id for item in result.artifact_aspects] == list(PRD_WEIGHTS)
    report = tmp_path / "report.md"
    assert main([str(GAP), "--brd", str(document), "--output", str(report)]) == 0
    text = report.read_text(encoding="utf-8")
    assert "# Skill and generated BRD evaluation — /brd" in text
    assert "## Generated BRD" in text
    assert "| Aspect | Weight | G-Eval | Schema | Aspect score |" in text
