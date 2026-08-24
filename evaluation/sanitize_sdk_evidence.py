"""Publica evidencia auditable del SDK sin prompts internos ni credenciales."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SECRET_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"sk-(?:proj-)?[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[0-9A-Za-z._-]{20,}", re.IGNORECASE),
)
METRICS = ("groundedness", "relevance")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} debe contener un objeto JSON")
    return data


def _evaluator(row: dict[str, Any], metric: str) -> dict[str, Any]:
    prefix = f"outputs.{metric}."
    properties = row.get(f"{prefix}{metric}_properties", {})
    if not isinstance(properties, dict):
        properties = {}
    return {
        "score": row.get(f"{prefix}{metric}"),
        "passed": row.get(f"{prefix}{metric}_passed"),
        "result": row.get(f"{prefix}{metric}_result"),
        "reason": row.get(f"{prefix}{metric}_reason"),
        "status": row.get(f"{prefix}{metric}_status"),
        "threshold": row.get(f"{prefix}{metric}_threshold"),
        "usage": {
            key: properties.get(key)
            for key in (
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "finish_reason",
                "model",
            )
        },
    }


def sanitize(raw_path: Path, canonical_path: Path) -> dict[str, Any]:
    raw = _load(raw_path)
    canonical = _load(canonical_path)
    raw_rows = raw.get("rows")
    canonical_rows = canonical.get("rows")
    if not isinstance(raw_rows, list) or not isinstance(canonical_rows, list):
        raise ValueError("raw y canonical deben contener rows")
    if len(raw_rows) != len(canonical_rows):
        raise ValueError("raw y canonical tienen cantidades de filas distintas")

    run = canonical.get("run", {})
    provider = run.get("provider", {}) if isinstance(run, dict) else {}
    rows: list[dict[str, Any]] = []
    for raw_row, canonical_row in zip(raw_rows, canonical_rows, strict=True):
        if raw_row.get("inputs.case_id") != canonical_row.get("case_id"):
            raise ValueError("raw y canonical no están alineados por case_id")
        rows.append(
            {
                "case_id": raw_row.get("inputs.case_id"),
                "segment": raw_row.get("inputs.segment"),
                "query": raw_row.get("inputs.query"),
                "context": raw_row.get("inputs.context"),
                "response": raw_row.get("inputs.response"),
                "expected_behavior": raw_row.get("inputs.expected_behavior"),
                "requires_refusal": raw_row.get("inputs.requires_refusal"),
                "forbidden_markers": raw_row.get("inputs.forbidden_markers"),
                "sdk_evaluators": {metric: _evaluator(raw_row, metric) for metric in METRICS},
                "deterministic_scores": {
                    key: value
                    for key, value in canonical_row.get("scores", {}).items()
                    if key not in METRICS
                },
            }
        )

    evidence = {
        "schema_version": "1.0",
        "evidence_type": "sanitized_azure_ai_evaluation_sdk_output",
        "sanitization": {
            "removed": [
                "SDK internal evaluator request/response samples",
                "studio_url",
                "credentials and request headers",
            ],
            "raw_sha256": _sha256(raw_path),
            "canonical_sha256": _sha256(canonical_path),
        },
        "run": {
            "status": run.get("status"),
            "variant": run.get("variant"),
            "evaluated_at": run.get("evaluated_at"),
            "provider": provider.get("provider"),
            "model": provider.get("model"),
            "pf_worker_count": run.get("pf_worker_count"),
        },
        "aggregate_metrics": raw.get("metrics", {}),
        "rows": rows,
    }
    serialized = json.dumps(evidence, ensure_ascii=False)
    if any(pattern.search(serialized) for pattern in SECRET_PATTERNS):
        raise ValueError("la evidencia sanitizada todavía contiene un patrón de secreto")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = sanitize(args.raw, args.canonical)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
