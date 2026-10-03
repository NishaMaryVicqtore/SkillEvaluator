from pathlib import Path

from skill_evaluator.cli import main
from skill_evaluator.evaluate import evaluate
from skill_evaluator.profiles import WEIGHTS

ROOT = Path(__file__).resolve().parents[1]
GOOD = ROOT / "tests" / "fixtures" / "good_prd" / "SKILL.md"
GAP = ROOT / "tests" / "fixtures" / "gap_brd" / "SKILL.md"
REAL_PRD = Path(r"C:\Users\nvicqto\.cursor\skills\prd\SKILL.md")
REAL_BRD = Path(r"C:\Users\nvicqto\.cursor\skills\brd\SKILL.md")


def _by_id(result):
    return {item.id: item for item in result.assertions}


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1) < 1e-9


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
