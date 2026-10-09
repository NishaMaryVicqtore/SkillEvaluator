from pathlib import Path
from shutil import copytree

from typer.testing import CliRunner

from tse import tier2_dedup
from tse.cli import app
from tse.tier1_static import run_tier1_scan
from tse.tier2_dedup import run_tier2_dedup
from tse.tier3_sandbox import run_tier3_sandbox


PROJECT_ROOT = Path(__file__).parents[1]
SAMPLES = PROJECT_ROOT / "samples"
runner = CliRunner()


def test_tier1_accepts_valid_and_rejects_insecure() -> None:
    valid = run_tier1_scan(SAMPLES / "trimble-connect-bcf-manager")
    insecure = run_tier1_scan(SAMPLES / "insecure-skill")

    assert valid.passed
    assert valid.violations == []
    assert not insecure.passed
    assert any("author" in violation for violation in insecure.violations)
    assert any("admin.all" in violation for violation in insecure.violations)
    assert any("Prompt injection" in violation for violation in insecure.violations)


def test_tier1_detects_secret_in_nested_python(tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    copytree(SAMPLES / "trimble-connect-bcf-manager", skill)
    nested = skill / "scripts"
    nested.mkdir()
    (nested / "unsafe.py").write_text(
        'api_key="demo-secret-value"\n',
        encoding="utf-8",
    )

    result = run_tier1_scan(skill)

    assert not result.passed
    assert any("API key assignment" in violation for violation in result.violations)


def test_tier2_version_duplicate_and_unique(monkeypatch) -> None:
    monkeypatch.setattr(tier2_dedup, "_fastembed_scores", lambda texts: None)

    update = run_tier2_dedup(SAMPLES / "trimble-connect-bcf-manager")
    duplicate = run_tier2_dedup(SAMPLES / "my-custom-bcf-helper")
    unique = run_tier2_dedup(SAMPLES / "low-uplift-skill")

    assert update.status == "VERSION_UPDATE"
    assert update.previous_composite_score == 85.0
    assert duplicate.status == "REJECTED_DUPLICATE"
    assert duplicate.max_similarity_score >= 0.85
    assert duplicate.similarity_backend == "tfidf-local"
    assert unique.status == "PASSED_UNIQUE"


def test_tier3_passes_uplift_and_rejects_low_uplift() -> None:
    verified = run_tier3_sandbox(SAMPLES / "trimble-connect-bcf-manager")
    low_uplift = run_tier3_sandbox(SAMPLES / "low-uplift-skill")

    assert verified.passed
    assert verified.composite_score >= 80.0
    assert verified.uplift_score >= 15.0
    assert verified.case_count == 4
    assert not low_uplift.passed
    assert low_uplift.uplift_score < 15.0


def test_validate_generates_verified_benchmark(tmp_path: Path) -> None:
    skill = tmp_path / "trimble-connect-bcf-manager"
    copytree(SAMPLES / "trimble-connect-bcf-manager", skill)
    benchmark = skill / "BENCHMARK.md"
    benchmark.unlink(missing_ok=True)

    result = runner.invoke(app, ["validate", str(skill), "--demo"])

    assert result.exit_code == 0, result.output
    assert benchmark.is_file()
    report = benchmark.read_text(encoding="utf-8")
    assert "PASSED VERIFIED SKILL" in report
    assert "Control composite" in report
    assert "Uplift" in report
    assert "Skill hash" in report


def test_pipeline_failure_exit_codes(tmp_path: Path) -> None:
    insecure = tmp_path / "insecure-skill"
    duplicate = tmp_path / "my-custom-bcf-helper"
    copytree(SAMPLES / "insecure-skill", insecure)
    copytree(SAMPLES / "my-custom-bcf-helper", duplicate)

    scan_result = runner.invoke(app, ["scan", str(insecure)])
    duplicate_result = runner.invoke(app, ["validate", str(duplicate), "--demo"])
    no_demo_result = runner.invoke(
        app,
        ["validate", str(duplicate), "--no-demo"],
    )

    assert scan_result.exit_code == 1
    assert duplicate_result.exit_code == 1
    assert "REJECTED_DUPLICATE" in duplicate_result.output
    assert no_demo_result.exit_code == 2
