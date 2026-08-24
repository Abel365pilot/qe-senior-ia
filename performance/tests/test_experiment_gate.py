import copy
import json
from pathlib import Path

import pytest

from validate_experiment import InvalidEvidence, validate_summary


ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "experiment_policy.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "relative_path",
    [
        "results/smoke-20260824-170803/summary.json",
        "results/smoke-20260824-170904/summary.json",
        "results/saturation-20260824-171114/summary.json",
        "results/control-20260824-172019/summary.json",
    ],
)
def test_versioned_evidence_satisfies_its_experiment_policy(relative_path):
    summary = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
    result = validate_summary(summary, POLICY)
    assert result["passed"], result["failures"]


def test_smoke_gate_rejects_a_single_capacity_failure():
    summary = json.loads(
        (ROOT / "results/smoke-20260824-170904/summary.json").read_text(encoding="utf-8")
    )
    broken = copy.deepcopy(summary)
    broken["aggregate"]["error_percentage"] = 0.1
    result = validate_summary(broken, POLICY)
    assert not result["passed"]
    assert any("error" in failure for failure in result["failures"])


def test_saturation_gate_rejects_an_experiment_that_never_reaches_429():
    summary = json.loads(
        (ROOT / "results/saturation-20260824-171114/summary.json").read_text(
            encoding="utf-8"
        )
    )
    broken = copy.deepcopy(summary)
    broken["history"]["first_failure"] = None
    result = validate_summary(broken, POLICY)
    assert not result["passed"]
    assert any("429" in failure for failure in result["failures"])


def test_gate_fails_closed_when_history_is_missing():
    summary = json.loads(
        (ROOT / "results/control-20260824-172019/summary.json").read_text(encoding="utf-8")
    )
    summary["history"] = {"available": False}
    with pytest.raises(InvalidEvidence, match="no está disponible"):
        validate_summary(summary, POLICY)
