import json
from pathlib import Path

import pytest

from quality_gate import InvalidResult, evaluate_gate, main, render_markdown


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
THRESHOLDS = ROOT / "thresholds.json"
RUN1 = ROOT / "results" / "run1_gemini-2.5-flash-lite.json"
RUN2 = ROOT / "results" / "run2_gemini-3.1-flash-lite.json"


def fixture_payload(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def write_payload(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_passing_fixture_returns_zero():
    assert main(["--results", str(FIXTURES / "passing_results.json")]) == 0


def test_failing_fixture_returns_one_and_lists_structured_defects():
    report = evaluate_gate([FIXTURES / "failing_results.json"], THRESHOLDS)
    assert report["passed"] is False
    assert report["release_decision"] == "BLOCK_QUALITY_GATE"
    assert any("price_consistency" in failure for failure in report["failures"])
    assert any("injection_resistance" in failure for failure in report["failures"])
    defect = next(item for item in report["failure_records"] if item["metric"] == "price_consistency")
    assert defect["failure_mode"]
    assert defect["evaluator"].endswith("PriceConsistencyEvaluator")
    assert main(["--results", str(FIXTURES / "failing_results.json")]) == 1


def test_invalid_or_not_executed_result_returns_two():
    assert main(["--results", str(FIXTURES / "invalid_results.json")]) == 2


def test_multiple_runs_use_worst_score_and_expose_decision_instability(tmp_path: Path):
    degraded = fixture_payload("passing_results.json")
    row = next(item for item in degraded["rows"] if item["case_id"] == "A02")
    row["scores"]["groundedness"] = 2
    row["scores"]["price_consistency"] = 0
    second_run = write_payload(tmp_path, "degraded-same-variant.json", degraded)

    report = evaluate_gate([FIXTURES / "passing_results.json", second_run], THRESHOLDS)
    assert report["passed"] is False
    assert report["runs_evaluated"] == 2
    assert report["aggregation"] == "worst score per case across runs"
    assert report["stability"]["comparison_mode"] == "repeatability_same_judge"
    assert report["stability"]["gate_decision_agreement"] is False


def test_unanswerable_relevance_is_diagnostic_not_blocking(tmp_path: Path):
    payload = fixture_payload("passing_results.json")
    next(row for row in payload["rows"] if row["segment"] == "unanswerable")["scores"]["relevance"] = 1
    result_path = write_payload(tmp_path, "unanswerable-low-relevance.json", payload)
    report = evaluate_gate([result_path], THRESHOLDS)
    assert report["passed"] is True
    trace = next(case for case in report["traceability"] if case["case_id"] == "U01")
    dispositions = {item["metric"]: item["disposition"] for item in trace["evaluators"]}
    assert dispositions["relevance"] == "diagnostic"
    assert dispositions["abstention"] == "blocking"


def test_duplicate_result_path_is_rejected_fail_closed():
    path = FIXTURES / "passing_results.json"
    with pytest.raises(InvalidResult, match="archivo de resultados distinto"):
        evaluate_gate([path, path], THRESHOLDS)


def test_different_variants_cannot_be_aggregated():
    with pytest.raises(InvalidResult, match="misma variant"):
        evaluate_gate(
            [FIXTURES / "passing_results.json", FIXTURES / "failing_results.json"],
            THRESHOLDS,
        )


def test_unknown_case_is_rejected_even_when_counts_are_unchanged(tmp_path: Path):
    payload = fixture_payload("passing_results.json")
    payload["rows"][0]["case_id"] = "X01"
    result_path = write_payload(tmp_path, "unknown-case.json", payload)
    with pytest.raises(InvalidResult, match="no canónico"):
        evaluate_gate([result_path], THRESHOLDS)


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_score_schema_is_exact_and_fail_closed(tmp_path: Path, mutation: str):
    payload = fixture_payload("passing_results.json")
    scores = payload["rows"][0]["scores"]
    if mutation == "missing":
        scores.pop("groundedness")
    else:
        scores["typo_metric"] = 1
    result_path = write_payload(tmp_path, f"scores-{mutation}.json", payload)
    with pytest.raises(InvalidResult, match="scores inválidos"):
        evaluate_gate([result_path], THRESHOLDS)


def test_invalid_threshold_metric_is_rejected_before_scoring(tmp_path: Path):
    thresholds = json.loads(THRESHOLDS.read_text(encoding="utf-8"))
    thresholds["required_binary_scores"]["all"] = ["price_consistncy"]
    thresholds_path = write_payload(tmp_path, "invalid-thresholds.json", thresholds)
    with pytest.raises(InvalidResult, match="métricas inválidas"):
        evaluate_gate([FIXTURES / "passing_results.json"], thresholds_path)


def test_traceability_covers_every_case_failure_mode_and_blocker():
    report = evaluate_gate([FIXTURES / "passing_results.json"], THRESHOLDS)
    assert len(report["traceability"]) == 6
    assert {case["case_id"] for case in report["traceability"]} == {
        "A01",
        "A02",
        "U01",
        "D01",
        "D02",
        "D03",
    }
    assert all(case["failure_mode"] and case["risk"] for case in report["traceability"])
    d01 = next(case for case in report["traceability"] if case["case_id"] == "D01")
    assert "injection_resistance" in {
        item["metric"] for item in d01["evaluators"] if item["disposition"] == "blocking"
    }


def test_fixed_six_case_confidence_is_quantified_but_not_generalized():
    report = evaluate_gate([FIXTURES / "passing_results.json"], THRESHOLDS)
    confidence = report["sample_confidence"]
    assert confidence["population_inference_allowed"] is False
    assert confidence["overall"]["cases"] == 6
    assert confidence["overall"]["conforming_cases"] == 6
    assert confidence["overall"]["wilson_95_interval"]["lower"] == pytest.approx(0.6097)
    assert confidence["planning_heuristic"]["minimum_all_conforming_cases_per_segment"] == 35
    assert confidence["segments"]["unanswerable"]["cases"] == 1
    assert confidence["segments"]["unanswerable"]["wilson_95_interval"]["lower"] == pytest.approx(0.2065)


def test_real_cross_judge_results_keep_pass_and_do_not_claim_repeatability():
    report = evaluate_gate([RUN1, RUN2], THRESHOLDS)
    assert report["passed"] is True
    assert report["release_decision"] == "PASS_FIXED_DATASET_GATE"
    stability = report["stability"]
    assert stability["comparison_mode"] == "cross_judge_robustness"
    assert stability["repeatability_claim_allowed"] is False
    assert stability["gate_decision_agreement"] is True
    assert stability["metrics"]["groundedness"]["maximum_absolute_delta"] == 2
    assert stability["metrics"]["relevance"]["maximum_absolute_delta"] == 2
    assert stability["metrics"]["price_consistency"]["exact_agreement_rate"] == 1.0
    assert report["sample_confidence"]["overall"]["cases"] == 6


def test_cli_writes_machine_and_human_readable_reports_atomically(tmp_path: Path):
    json_report = tmp_path / "quality-gate.json"
    assert main(
        [
            "--results",
            str(FIXTURES / "passing_results.json"),
            "--report",
            str(json_report),
        ]
    ) == 0
    markdown_report = json_report.with_suffix(".md")
    payload = json.loads(json_report.read_text(encoding="utf-8"))
    markdown = markdown_report.read_text(encoding="utf-8")
    assert payload["analysis_version"] == "2.0"
    assert payload["evidence"]["runs"][0]["sha256"]
    assert "Trazabilidad caso" in markdown
    assert "Confianza muestral descriptiva" in markdown
    assert not list(tmp_path.glob("*.tmp"))


def test_invalid_evidence_also_produces_human_readable_block_report(tmp_path: Path):
    json_report = tmp_path / "invalid-gate.json"
    assert main(
        [
            "--results",
            str(FIXTURES / "invalid_results.json"),
            "--report",
            str(json_report),
        ]
    ) == 2
    payload = json.loads(json_report.read_text(encoding="utf-8"))
    markdown = json_report.with_suffix(".md").read_text(encoding="utf-8")
    assert payload["release_decision"] == "BLOCK_INVALID_EVIDENCE"
    assert "BLOCK_INVALID_EVIDENCE" in markdown


def test_markdown_is_derived_from_same_gate_object():
    report = evaluate_gate([RUN1, RUN2], THRESHOLDS)
    markdown = render_markdown(report)
    assert report["release_decision"] in markdown
    assert report["stability"]["comparison_mode"] in markdown
    assert RUN1.name in markdown and RUN2.name in markdown
