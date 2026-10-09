from pathlib import Path
from shutil import copytree

from skill_evaluator.cli import main
from skill_evaluator.evaluate import evaluate_governance
from skill_evaluator.governance_eval import GEVAL_LABEL, GRAPH_LABEL, SCHEMA_LABEL

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples" / "workride-agl"


def test_governance_assets_use_the_three_algorithms() -> None:
    result = evaluate_governance(SAMPLE)
    kinds = {item.role.split(" — ", 1)[0] for item in result.subjects}
    assert kinds == {"Policy", "Rule", "Skill", "Eval", "Architecture skill"}
    for subject in result.subjects:
        assert [item.label for item in subject.algorithms] == [SCHEMA_LABEL, GEVAL_LABEL, GRAPH_LABEL]
        assert [item.id for item in subject.algorithms] == ["schema", "geval", "structure"]
        deadlock = next(item for item in subject.algorithms[2].criteria if item.id == "deadlock")
        assert 1 <= deadlock.score <= 5
    assert result.combined == sum(item.score for item in result.subjects) / len(result.subjects)
    cycled = [
        subject.role
        for subject in result.subjects
        if any(item.score == 1 for item in subject.algorithms[2].criteria if item.id == "deadlock")
    ]
    assert any("validate-booking-rules" in name for name in cycled)
    assert any("validate-chat-override" in name for name in cycled)


def test_governance_schema_reports_true_was_expected(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    copytree(SAMPLE, root)
    policy = root / ".ai-governance" / "global-security-policy.md"
    policy.write_text("# Notes\n\nKeep going.\n", encoding="utf-8")
    result = evaluate_governance(root)
    assert result.schema_errors
    assert any("True was expected" in message for message in result.schema_errors)


def test_governance_cli_writes_the_three_algorithm_report(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    payload = tmp_path / "report.json"
    exit_code = main(
        [
            "--governance",
            str(SAMPLE),
            "--report",
            str(report),
            "--json",
            str(payload),
        ]
    )
    assert exit_code == 0
    text = report.read_text(encoding="utf-8")
    assert SCHEMA_LABEL in text
    assert GEVAL_LABEL in text
    assert GRAPH_LABEL in text
    assert "Deadlocks" in text
    assert "Steps:" in text
    assert "Evidence from the" in text
    assert "No secret marker is hardcoded: " in text
    assert '"mode": "governance"' in payload.read_text(encoding="utf-8")
