from pathlib import Path

import pytest

from skill_evaluator.architect_eval import GEVAL_WEIGHTS
from skill_evaluator.cli import main
from skill_evaluator.evaluate import evaluate

ROOT = Path(__file__).resolve().parents[1]
GOOD = ROOT / "tests" / "fixtures" / "good_architect" / "SKILL.md"
GAP = ROOT / "tests" / "fixtures" / "gap_architect" / "SKILL.md"
DESIGN = ROOT / "tests" / "fixtures" / "generated" / "good_design.md"
TANGLED = ROOT / "tests" / "fixtures" / "generated" / "tangled_design.md"
BRD = ROOT / "tests" / "fixtures" / "gap_brd" / "SKILL.md"
REAL = Path(r"C:\Users\nvicqto\.cursor\skills\architect\SKILL.md")


def _algorithm(result, algorithm_id, design=False):
    group = result.design_algorithms if design else result.algorithms
    return next(item for item in group if item.id == algorithm_id)


def test_geval_weights_sum_to_one():
    assert abs(sum(GEVAL_WEIGHTS.values()) - 1) < 1e-9


def test_architecture_skill_scores_three_algorithms():
    result = evaluate(GOOD)
    assert result.profile.id == "architect"
    assert [item.id for item in result.algorithms] == ["schema", "geval", "structure"]
    assert result.schema_errors == []
    assert all(item.score == 5 for item in result.algorithms)
    assert result.combined == 5
    assert result.verdict == "Strong"
    deadlock = next(item for item in _algorithm(result, "structure").criteria if item.id == "deadlock")
    assert deadlock.score == 5


def test_gap_architecture_skill_fails_deadlock_and_schema():
    result = evaluate(GAP)
    assert result.combined < 5
    assert any("True was expected" in message for message in result.schema_errors)
    structure = _algorithm(result, "structure")
    deadlock = next(item for item in structure.criteria if item.id == "deadlock")
    orphan = next(item for item in structure.criteria if item.id == "orphan")
    assert deadlock.score == 1
    assert orphan.score == 3
    boundaries = next(item for item in _algorithm(result, "geval").criteria if item.id == "security_boundaries")
    assert boundaries.score <= 2
    assert result.verdict.startswith("Below the acceptable line")


def test_skill_and_design_average_the_three_algorithms():
    result = evaluate(GOOD, design=DESIGN)
    assert result.design_path
    assert all(item.score == 5 for item in result.design_algorithms)
    assert result.design_combined == 5
    assert result.combined == 5
    tangled = evaluate(GOOD, design=TANGLED)
    assert _algorithm(tangled, "structure", design=True).score < 3
    assert tangled.combined < tangled.skill_combined
    assert tangled.combined == (tangled.skill_combined + tangled.design_combined) / 2


def test_skill_and_design_keep_every_aspect():
    result = evaluate(GOOD, design=DESIGN)
    names = [item.criterion for algorithm in result.subjects[0].algorithms for item in algorithm.criteria]
    assert "Feasibility" in names
    assert "Security boundaries" in names
    assert "Deadlocks" in names
    assert "Orphan modules" in names
    assert "Coupling density" in names
    document_names = [item.criterion for algorithm in result.subjects[1].algorithms for item in algorithm.criteria]
    assert document_names == names


def test_separate_skills_and_documents_are_all_scored():
    result = evaluate(GOOD, design_skill=GAP, architect_doc=DESIGN, design_doc=TANGLED)
    assert [item.role for item in result.subjects] == [
        "Architecture skill",
        "Design skill",
        "Architecture document",
        "Design document",
    ]
    assert all(len(item.algorithms) == 3 for item in result.subjects)
    assert result.combined == sum(item.score for item in result.subjects) / 4
    assert _algorithm(result, "structure", design=True).score == 5
    tangled = next(item for item in result.subjects if item.role == "Design document")
    assert next(item for item in tangled.algorithms if item.id == "structure").score < 3


def test_prompt_asks_skill_or_skill_and_document(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("skill_evaluator.cli._interactive", lambda: True)
    answers = iter(["nope", "2", "", str(DESIGN)])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    report = tmp_path / "report.md"
    exit_code = main([str(GOOD), "--output", str(report)])
    assert exit_code == 0
    text = report.read_text(encoding="utf-8")
    assert "Topological Graph Validation" in text or "Topological graph validation" in text
    assert "Architect and design skill" in text
    assert "Architecture and design document" in text
    assert "Feasibility" in text
    assert "Deadlocks" in text


def test_noninteractive_architecture_run_scores_the_skill(monkeypatch):
    monkeypatch.setattr("skill_evaluator.cli._interactive", lambda: False)
    assert main([str(GOOD)]) == 0


def test_design_requires_an_architecture_skill():
    with pytest.raises(ValueError, match="architecture skill"):
        evaluate(BRD, design=DESIGN)


def test_cli_scores_architecture_skill_and_design(tmp_path: Path):
    markdown = tmp_path / "report.md"
    payload = tmp_path / "report.json"
    exit_code = main(
        [
            str(GOOD),
            "--design",
            str(DESIGN),
            "--output",
            str(markdown),
            "--json",
            str(payload),
            "--fail-under",
            "4.5",
        ]
    )
    assert exit_code == 0
    text = markdown.read_text(encoding="utf-8")
    assert "Schema parser" in text
    assert "Topological graph validation" in text
    assert "Deadlocks" in text
    body = payload.read_text(encoding="utf-8")
    assert '"mode": "skill+design"' in body
    refused = main([str(BRD), "--design", str(DESIGN)])
    assert refused == 2


def test_cli_accepts_separate_skill_and_document_paths(tmp_path: Path):
    report = tmp_path / "report.md"
    exit_code = main(
        [
            "--architect-skill",
            str(GOOD),
            "--design-skill",
            str(GAP),
            "--architect-doc",
            str(DESIGN),
            "--design-doc",
            str(TANGLED),
            "--output",
            str(report),
        ]
    )
    assert exit_code == 0
    text = report.read_text(encoding="utf-8")
    for role in ("Architecture skill", "Design skill", "Architecture document", "Design document"):
        assert role in text
    assert "Feasibility" in text
    assert "Security boundaries" in text
    assert "Deadlocks" in text
    assert "Orphan modules" in text
    assert "Coupling density" in text


def test_real_architect_skill_runs():
    if not REAL.is_file():
        return
    result = evaluate(REAL)
    assert result.profile.id == "architect"
    assert [item.id for item in result.algorithms] == ["schema", "geval", "structure"]
    assert all(0 <= item.score <= 5 for item in result.algorithms)
