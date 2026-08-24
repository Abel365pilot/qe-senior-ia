import json
from pathlib import Path

import pytest

from quality_gate import InvalidResult, evaluate_gate, main


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
THRESHOLDS = ROOT / "thresholds.json"


def test_passing_fixture_returns_zero():
    assert main(["--results", str(FIXTURES / "passing_results.json")]) == 0


def test_failing_fixture_returns_one_and_lists_defects():
    report = evaluate_gate([FIXTURES / "failing_results.json"], THRESHOLDS)
    assert report["passed"] is False
    assert any("price_consistency" in failure for failure in report["failures"])
    assert any("injection_resistance" in failure for failure in report["failures"])
    assert main(["--results", str(FIXTURES / "failing_results.json")]) == 1


def test_invalid_or_not_executed_result_returns_two():
    assert main(["--results", str(FIXTURES / "invalid_results.json")]) == 2


def test_multiple_runs_use_worst_score_per_case():
    report = evaluate_gate(
        [FIXTURES / "passing_results.json", FIXTURES / "failing_results.json"], THRESHOLDS
    )
    assert report["passed"] is False
    assert report["runs_evaluated"] == 2
    assert report["aggregation"] == "worst score per case across runs"


def test_unanswerable_relevance_is_diagnostic_not_blocking(tmp_path: Path):
    payload = json.loads((FIXTURES / "passing_results.json").read_text(encoding="utf-8"))
    next(row for row in payload["rows"] if row["segment"] == "unanswerable")["scores"]["relevance"] = 1
    result_path = tmp_path / "unanswerable-low-relevance.json"
    result_path.write_text(json.dumps(payload), encoding="utf-8")
    report = evaluate_gate([result_path], THRESHOLDS)
    assert report["passed"] is True
