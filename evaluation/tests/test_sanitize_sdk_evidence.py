import json
from pathlib import Path

import pytest

from sanitize_sdk_evidence import sanitize


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_sanitizer_keeps_reason_and_usage_but_removes_sdk_prompt(tmp_path):
    raw = {
        "rows": [
            {
                "inputs.case_id": "A01",
                "inputs.segment": "answerable",
                "inputs.query": "q",
                "inputs.context": "c",
                "inputs.response": "r",
                "inputs.expected_behavior": "answer_from_context",
                "inputs.requires_refusal": False,
                "inputs.forbidden_markers": "",
                "outputs.groundedness.groundedness": 5,
                "outputs.groundedness.groundedness_passed": True,
                "outputs.groundedness.groundedness_result": "pass",
                "outputs.groundedness.groundedness_reason": "grounded",
                "outputs.groundedness.groundedness_status": "completed",
                "outputs.groundedness.groundedness_threshold": 3,
                "outputs.groundedness.groundedness_properties": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                    "finish_reason": "stop",
                    "model": "judge",
                    "sample_input": "private evaluator prompt",
                },
            }
        ],
        "metrics": {"groundedness.groundedness": 5},
        "studio_url": "https://not-published.invalid",
    }
    canonical = {
        "run": {
            "status": "completed",
            "variant": "good",
            "evaluated_at": "2026-08-24T00:00:00Z",
            "provider": {"provider": "test", "model": "judge"},
            "pf_worker_count": 1,
        },
        "rows": [{"case_id": "A01", "scores": {"groundedness": 5, "abstention": 1}}],
    }

    result = sanitize(_write(tmp_path / "raw.json", raw), _write(tmp_path / "canonical.json", canonical))
    serialized = json.dumps(result)

    assert result["rows"][0]["sdk_evaluators"]["groundedness"]["reason"] == "grounded"
    assert result["rows"][0]["sdk_evaluators"]["groundedness"]["usage"]["total_tokens"] == 12
    assert result["rows"][0]["deterministic_scores"] == {"abstention": 1}
    assert "private evaluator prompt" not in serialized
    assert "https://not-published.invalid" not in serialized
    assert "studio_url" not in result


def test_sanitizer_rejects_misaligned_rows(tmp_path):
    raw = _write(tmp_path / "raw.json", {"rows": [{"inputs.case_id": "A01"}]})
    canonical = _write(tmp_path / "canonical.json", {"run": {}, "rows": [{"case_id": "A02"}]})

    with pytest.raises(ValueError, match="alineados"):
        sanitize(raw, canonical)
