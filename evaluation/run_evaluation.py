"""Ejecuta Groundedness/Relevance y controles deterministas sobre respuestas sembradas."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from evaluators import AbstentionEvaluator, InjectionResistanceEvaluator, PriceConsistencyEvaluator
from gemini_compat_proxy import gemini_compatible_settings
from provider_factory import ProviderConfigError, build_model_config, load_provider_settings


ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = ROOT / "data" / "evaluation_cases.jsonl"
DEBUG_DATASET = ROOT / "data" / "debug_2rows.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL inválido en {path.name}:{line_number}") from exc
    if not rows:
        raise ValueError(f"El dataset {path} está vacío.")
    return rows


def resolve_seeded_rows(path: Path, variant: str) -> list[dict[str, Any]]:
    source = _read_jsonl(path)
    response_key = "response" if variant == "good" else "response_bad"
    resolved: list[dict[str, Any]] = []
    for row in source:
        required = {"case_id", "segment", "query", "context", response_key, "expected_behavior"}
        missing = sorted(required - row.keys())
        if missing:
            raise ValueError(f"{row.get('case_id', '<sin-id>')} carece de: {', '.join(missing)}")
        resolved.append(
            {
                "case_id": row["case_id"],
                "segment": row["segment"],
                "query": row["query"],
                "context": row["context"],
                "response": row[response_key],
                "expected_behavior": row["expected_behavior"],
                "requires_refusal": row.get("requires_refusal", False),
                "forbidden_markers": row.get("forbidden_markers", ""),
            }
        )
    return resolved


def _score(raw_row: dict[str, Any], alias: str, metric: str) -> float | None:
    exact = (
        f"outputs.{alias}.{metric}",
        f"outputs.{alias}.gpt_{metric}",
        f"outputs.{metric}.{metric}",
    )
    for key in exact:
        value = raw_row.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    suffix = f".{metric}"
    for key, value in raw_row.items():
        if key.startswith(f"outputs.{alias}.") and key.endswith(suffix) and isinstance(value, (int, float)):
            return float(value)
    return None


def _canonicalize(
    sdk_result: Any,
    cases: list[dict[str, Any]],
    variant: str,
    provider_summary: dict[str, object],
) -> dict[str, object]:
    raw_rows = list(sdk_result.get("rows", []))
    if len(raw_rows) != len(cases):
        raise ValueError(f"El SDK devolvió {len(raw_rows)} filas para {len(cases)} casos.")
    rows: list[dict[str, object]] = []
    for case, raw in zip(cases, raw_rows, strict=True):
        rows.append(
            {
                "case_id": case["case_id"],
                "segment": case["segment"],
                "variant": variant,
                "scores": {
                    "groundedness": _score(raw, "groundedness", "groundedness"),
                    "relevance": _score(raw, "relevance", "relevance"),
                    "price_consistency": _score(raw, "price_consistency", "price_consistency"),
                    "abstention": _score(raw, "abstention", "abstention"),
                    "injection_resistance": _score(raw, "injection_resistance", "injection_resistance"),
                },
            }
        )
    return {
        "schema_version": "1.0",
        "run": {
            "status": "completed",
            "variant": variant,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "provider": provider_summary,
            "pf_worker_count": int(os.environ["PF_WORKER_COUNT"]),
        },
        "aggregate_metrics": dict(sdk_result.get("metrics", {})),
        "rows": rows,
    }


def _apply_deterministic_scores(sdk_result: Any, cases: list[dict[str, Any]]) -> None:
    raw_rows = list(sdk_result.get("rows", []))
    if len(raw_rows) != len(cases):
        raise ValueError(f"El SDK devolvió {len(raw_rows)} filas para {len(cases)} casos.")
    price = PriceConsistencyEvaluator()
    abstention = AbstentionEvaluator()
    injection = InjectionResistanceEvaluator()
    for raw, case in zip(raw_rows, cases, strict=True):
        results = {
            "price_consistency": price(response=case["response"], context=case["context"]),
            "abstention": abstention(
                response=case["response"],
                expected_behavior=case["expected_behavior"],
                forbidden_markers=case["forbidden_markers"],
            ),
            "injection_resistance": injection(
                response=case["response"],
                segment=case["segment"],
                requires_refusal=case["requires_refusal"],
                forbidden_markers=case["forbidden_markers"],
            ),
        }
        for alias, values in results.items():
            for key, value in values.items():
                raw[f"outputs.{alias}.{key}"] = value


def run(dataset: Path, variant: str, output_dir: Path) -> Path:
    os.environ["PF_WORKER_COUNT"] = "1"
    load_dotenv(ROOT.parent / ".env", override=False)
    cases = resolve_seeded_rows(dataset, variant)
    settings = load_provider_settings()
    try:
        from azure.ai.evaluation import GroundednessEvaluator, RelevanceEvaluator, evaluate
    except ImportError as exc:
        raise ProviderConfigError("No está instalado azure-ai-evaluation.") from exc

    common = {
        "query": "${data.query}",
        "context": "${data.context}",
        "response": "${data.response}",
    }
    evaluator_config = {
        "groundedness": {"column_mapping": common},
        "relevance": {"column_mapping": common},
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    scope = "debug" if dataset.resolve() == DEBUG_DATASET.resolve() else "full"
    raw_path = output_dir / f"raw_{scope}_{variant}_{run_id}.json"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False) as handle:
        temp_path = Path(handle.name)
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")
    try:
        with gemini_compatible_settings(settings) as effective_settings:
            model_config = build_model_config(effective_settings)
            evaluators = {
                "groundedness": GroundednessEvaluator(model_config=model_config, threshold=3),
                "relevance": RelevanceEvaluator(model_config=model_config, threshold=3),
            }
            result = evaluate(
                data=str(temp_path),
                evaluators=evaluators,
                evaluator_config=evaluator_config,
                evaluation_name=f"qe-senior-ia-{variant}-{run_id}",
                output_path=str(raw_path),
                fail_on_evaluator_errors=True,
            )
            _apply_deterministic_scores(result, cases)
    finally:
        temp_path.unlink(missing_ok=True)
    canonical = _canonicalize(result, cases, variant, settings.safe_summary())
    result_path = output_dir / f"evaluation_{scope}_{variant}_{run_id}.json"
    result_path.write_text(json.dumps(canonical, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("good", "bad"), default="good")
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--debug", action="store_true", help="Usa solo dos filas para validar compatibilidad.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args(argv)
    dataset = args.dataset or (DEBUG_DATASET if args.debug else DEFAULT_DATASET)
    try:
        result_path = run(dataset.resolve(), args.variant, args.output_dir.resolve())
    except (ProviderConfigError, ValueError) as exc:
        print(f"CONFIGURATION_ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # El SDK/proveedor puede fallar por red, cuota o compatibilidad.
        print(f"EVALUATION_ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(result_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
