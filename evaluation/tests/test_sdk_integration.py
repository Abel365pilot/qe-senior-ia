import os

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_AZURE_SDK_INTEGRATION") != "1",
    reason="Opt-in: azure evaluate puede iniciar workers y no debe bloquear CI.",
)
pytest.importorskip("azure.ai.evaluation")
from run_evaluation import DEBUG_DATASET, _apply_deterministic_scores, _score, resolve_seeded_rows


def test_runner_merges_deterministic_evaluators_without_network():
    os.environ["PF_WORKER_COUNT"] = "1"
    rows = resolve_seeded_rows(DEBUG_DATASET, "good")
    result = {"rows": [{}, {}]}
    _apply_deterministic_scores(result, rows)
    assert _score(result["rows"][0], "price_consistency", "price_consistency") == 1.0
    assert _score(result["rows"][1], "injection_resistance", "injection_resistance") == 1.0
