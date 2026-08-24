"""Quality gate fail-closed. Códigos: 0 aprobado, 1 calidad insuficiente, 2 entrada inválida."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
DEFAULT_THRESHOLDS = ROOT / "thresholds.json"
DEFAULT_DATASET = ROOT / "data" / "evaluation_cases.jsonl"
DEFAULT_CONTRACT = ROOT / "quality_contract.json"
ANALYSIS_VERSION = "2.0"
SEGMENTS = ("answerable", "unanswerable", "adversarial")
REQUIRED_JUDGE_SCORES = ("groundedness", "relevance")
BINARY_SCORES = ("price_consistency", "abstention", "injection_resistance")
ALL_SCORES = REQUIRED_JUDGE_SCORES + BINARY_SCORES
Z_95 = 1.959963984540054


class InvalidResult(ValueError):
    """La evidencia no cumple el contrato mínimo y el gate debe bloquear."""


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise InvalidResult(f"{label} no es un número finito.")
    return float(value)


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise InvalidResult(f"{label} debe ser un entero positivo.")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidResult(f"clave JSON duplicada: {key!r}.")
        result[key] = value
    return result


def _loads_json(text: str, label: str) -> Any:
    try:
        return json.loads(text, object_pairs_hook=_unique_object)
    except InvalidResult as exc:
        raise InvalidResult(f"{label}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InvalidResult(f"{label}: JSON inválido: {exc}") from exc


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = _loads_json(path.read_text(encoding="utf-8"), label)
    except OSError as exc:
        raise InvalidResult(f"No se pudo leer {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise InvalidResult(f"{label} debe contener un objeto JSON.")
    return payload


def _sha256(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as exc:
        raise InvalidResult(f"No se pudo calcular SHA-256 de {path}: {exc}") from exc


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.name


def _require_mapping(mapping: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise InvalidResult(f"{label}.{key} debe ser un objeto.")
    return value


def validate_thresholds(payload: dict[str, Any]) -> dict[str, Any]:
    """Valida por completo la política para evitar defaults permisivos."""

    if payload.get("schema_version") != "1.0":
        raise InvalidResult("thresholds.schema_version debe ser '1.0'.")
    expected_count = _positive_int(payload.get("expected_case_count"), "expected_case_count")
    segment_counts = _require_mapping(payload, "expected_segment_counts", "thresholds")
    if set(segment_counts) != set(SEGMENTS):
        raise InvalidResult(f"expected_segment_counts debe declarar exactamente {list(SEGMENTS)}.")
    normalized_counts = {
        segment: _positive_int(segment_counts.get(segment), f"expected_segment_counts.{segment}")
        for segment in SEGMENTS
    }
    if sum(normalized_counts.values()) != expected_count:
        raise InvalidResult("La suma de expected_segment_counts no coincide con expected_case_count.")

    answerable = _require_mapping(payload, "answerable", "thresholds")
    for metric in REQUIRED_JUDGE_SCORES:
        row_min = _number(answerable.get(f"{metric}_row_min"), f"answerable.{metric}_row_min")
        average_min = _number(
            answerable.get(f"{metric}_average_min"), f"answerable.{metric}_average_min"
        )
        if not (1.0 <= row_min <= 5.0 and 1.0 <= average_min <= 5.0):
            raise InvalidResult(f"Los umbrales de {metric} deben estar entre 1 y 5.")
        if row_min > average_min:
            raise InvalidResult(f"answerable.{metric}_row_min no puede superar el promedio mínimo.")

    unanswerable = _require_mapping(payload, "unanswerable", "thresholds")
    if unanswerable.get("judge_metrics_mode") != "diagnostic_only":
        raise InvalidResult("unanswerable.judge_metrics_mode debe ser 'diagnostic_only'.")

    required = _require_mapping(payload, "required_binary_scores", "thresholds")
    allowed_scopes = {"all", *SEGMENTS}
    if not set(required).issubset(allowed_scopes) or "all" not in required:
        raise InvalidResult("required_binary_scores contiene un scope inválido o no declara 'all'.")
    for scope, metrics in required.items():
        if not isinstance(metrics, list) or any(not isinstance(metric, str) for metric in metrics):
            raise InvalidResult(f"required_binary_scores.{scope} debe ser una lista de métricas.")
        if len(metrics) != len(set(metrics)):
            raise InvalidResult(f"required_binary_scores.{scope} contiene métricas duplicadas.")
        unknown = set(metrics) - set(BINARY_SCORES)
        if unknown:
            raise InvalidResult(f"required_binary_scores.{scope} contiene métricas inválidas: {sorted(unknown)}.")
    return payload


def _blocking_metrics(segment: str, thresholds: dict[str, Any]) -> list[str]:
    required = thresholds["required_binary_scores"]
    metrics = list(required.get("all", [])) + list(required.get(segment, []))
    if segment == "answerable":
        metrics = list(REQUIRED_JUDGE_SCORES) + metrics
    return list(dict.fromkeys(metrics))


def load_dataset(path: Path, thresholds: dict[str, Any]) -> dict[str, dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise InvalidResult(f"No se pudo leer dataset {path}: {exc}") from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        row = _loads_json(line, f"{path.name}:{line_number}")
        if not isinstance(row, dict):
            raise InvalidResult(f"{path.name}:{line_number} debe ser un objeto.")
        rows.append(row)
    expected_count = int(thresholds["expected_case_count"])
    if len(rows) != expected_count:
        raise InvalidResult(f"{path.name}: se esperaban {expected_count} casos canónicos.")

    manifest: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    for row in rows:
        case_id = str(row.get("case_id", "")).strip()
        segment = str(row.get("segment", "")).strip()
        expected_behavior = str(row.get("expected_behavior", "")).strip()
        if not case_id or case_id in manifest:
            raise InvalidResult(f"{path.name}: case_id vacío o duplicado: {case_id!r}.")
        if segment not in SEGMENTS:
            raise InvalidResult(f"{path.name}: segmento inválido en {case_id}: {segment!r}.")
        if not expected_behavior:
            raise InvalidResult(f"{path.name}: expected_behavior ausente en {case_id}.")
        manifest[case_id] = {
            "case_id": case_id,
            "segment": segment,
            "expected_behavior": expected_behavior,
        }
        counts[segment] += 1
    expected_counts = Counter(
        {segment: int(count) for segment, count in thresholds["expected_segment_counts"].items()}
    )
    if counts != expected_counts:
        raise InvalidResult(f"{path.name}: distribución {dict(counts)}; esperada {dict(expected_counts)}.")
    return manifest


def load_quality_contract(
    path: Path,
    dataset: dict[str, dict[str, Any]],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    payload = _read_json_object(path, path.name)
    if payload.get("schema_version") != "1.0":
        raise InvalidResult("quality_contract.schema_version debe ser '1.0'.")
    evaluators = _require_mapping(payload, "evaluators", "quality_contract")
    if set(evaluators) != set(ALL_SCORES):
        raise InvalidResult(f"quality_contract.evaluators debe declarar exactamente {list(ALL_SCORES)}.")
    for name, definition in evaluators.items():
        if not isinstance(definition, dict):
            raise InvalidResult(f"quality_contract.evaluators.{name} debe ser un objeto.")
        expected_kind = "llm_judge" if name in REQUIRED_JUDGE_SCORES else "deterministic"
        if definition.get("kind") != expected_kind:
            raise InvalidResult(f"{name}.kind debe ser {expected_kind!r}.")
        for field in ("implementation", "failure_signal", "score_domain"):
            if not isinstance(definition.get(field), str) or not definition[field].strip():
                raise InvalidResult(f"quality_contract.evaluators.{name}.{field} es obligatorio.")

    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != len(dataset):
        raise InvalidResult("quality_contract.cases no coincide con el dataset canónico.")
    normalized_cases: dict[str, dict[str, Any]] = {}
    for case in cases:
        if not isinstance(case, dict):
            raise InvalidResult("Cada entrada de quality_contract.cases debe ser un objeto.")
        case_id = str(case.get("case_id", "")).strip()
        if not case_id or case_id in normalized_cases or case_id not in dataset:
            raise InvalidResult(f"quality_contract: case_id vacío, duplicado o desconocido: {case_id!r}.")
        canonical = dataset[case_id]
        if case.get("segment") != canonical["segment"]:
            raise InvalidResult(f"quality_contract: segmento divergente para {case_id}.")
        if case.get("expected_behavior") != canonical["expected_behavior"]:
            raise InvalidResult(f"quality_contract: expected_behavior divergente para {case_id}.")
        for field in ("failure_mode", "risk"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                raise InvalidResult(f"quality_contract: {field} ausente en {case_id}.")
        intended = case.get("evaluators")
        if not isinstance(intended, list) or not intended or any(not isinstance(x, str) for x in intended):
            raise InvalidResult(f"quality_contract: evaluators inválido en {case_id}.")
        if len(intended) != len(set(intended)) or set(intended) - set(ALL_SCORES):
            raise InvalidResult(f"quality_contract: evaluators duplicados o desconocidos en {case_id}.")
        missing_blockers = set(_blocking_metrics(canonical["segment"], thresholds)) - set(intended)
        if missing_blockers:
            raise InvalidResult(
                f"quality_contract: {case_id} no traza evaluadores bloqueantes: {sorted(missing_blockers)}."
            )
        normalized_cases[case_id] = {
            "case_id": case_id,
            "segment": canonical["segment"],
            "expected_behavior": canonical["expected_behavior"],
            "failure_mode": case["failure_mode"].strip(),
            "risk": case["risk"].strip(),
            "evaluators": intended,
        }
    if set(normalized_cases) != set(dataset):
        raise InvalidResult("quality_contract no contiene exactamente el manifiesto canónico.")
    return {"evaluators": evaluators, "cases": normalized_cases}


def _provider_metadata(provider: object, label: str) -> dict[str, Any]:
    if isinstance(provider, str):
        name = provider.strip()
        if not name:
            raise InvalidResult(f"{label}.provider está vacío.")
        return {"provider": name, "model": None, "judge_id": name}
    if not isinstance(provider, dict):
        raise InvalidResult(f"{label}.provider debe ser texto u objeto.")
    name = str(provider.get("provider", "")).strip()
    model = str(provider.get("model", "")).strip()
    if not name or not model:
        raise InvalidResult(f"{label}.provider debe declarar provider y model.")
    return {"provider": name, "model": model, "judge_id": f"{name}:{model}"}


def _validate_timestamp(value: object, label: str, required: bool) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise InvalidResult(f"{label} debe ser un timestamp ISO-8601.")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise InvalidResult(f"{label} no es ISO-8601 válido.") from exc
    if parsed.tzinfo is None:
        raise InvalidResult(f"{label} debe incluir zona horaria.")
    return value.strip()


def _load_result_document(
    path: Path,
    thresholds: dict[str, Any],
    dataset: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    payload = _read_json_object(path, path.name)
    if payload.get("schema_version") != "1.0":
        raise InvalidResult(f"{path.name}: schema_version inválido.")
    run = payload.get("run")
    if not isinstance(run, dict) or run.get("status") != "completed":
        raise InvalidResult(f"{path.name}: estado de ejecución no completado.")
    variant = str(run.get("variant", "")).strip()
    if not variant:
        raise InvalidResult(f"{path.name}: run.variant es obligatorio.")
    provider = _provider_metadata(run.get("provider"), f"{path.name}.run")
    evaluated_at = _validate_timestamp(
        run.get("evaluated_at"),
        f"{path.name}.run.evaluated_at",
        required=provider["model"] is not None,
    )
    worker_count = run.get("pf_worker_count")
    if worker_count is not None:
        _positive_int(worker_count, f"{path.name}.run.pf_worker_count")

    rows = payload.get("rows")
    expected_count = int(thresholds["expected_case_count"])
    if not isinstance(rows, list) or len(rows) != expected_count:
        raise InvalidResult(f"{path.name}: se esperaban {expected_count} filas completas.")
    ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise InvalidResult(f"{path.name}: fila {index} no es un objeto.")
        case_id = str(row.get("case_id", "")).strip()
        if not case_id or case_id in ids or case_id not in dataset:
            raise InvalidResult(f"{path.name}: case_id vacío, duplicado o no canónico: {case_id!r}.")
        segment = str(row.get("segment", "")).strip()
        if segment != dataset[case_id]["segment"]:
            raise InvalidResult(f"{path.name}: segmento divergente en {case_id}: {segment!r}.")
        row_variant = row.get("variant")
        if row_variant is not None and row_variant != variant:
            raise InvalidResult(f"{path.name}: variant divergente en {case_id}.")
        scores = row.get("scores")
        if not isinstance(scores, dict):
            raise InvalidResult(f"{path.name}: scores ausente en {case_id}.")
        if set(scores) != set(ALL_SCORES):
            missing = sorted(set(ALL_SCORES) - set(scores))
            extra = sorted(set(scores) - set(ALL_SCORES))
            raise InvalidResult(f"{path.name}: scores inválidos en {case_id}; faltan={missing}, sobran={extra}.")
        parsed = {name: _number(scores[name], f"{case_id}.{name}") for name in ALL_SCORES}
        for name in REQUIRED_JUDGE_SCORES:
            if not 1.0 <= parsed[name] <= 5.0:
                raise InvalidResult(f"{case_id}.{name} debe estar entre 1 y 5.")
        for name in BINARY_SCORES:
            if parsed[name] not in {0.0, 1.0}:
                raise InvalidResult(f"{case_id}.{name} debe ser binario (0/1).")
        ids.add(case_id)
        normalized.append({"case_id": case_id, "segment": segment, "scores": parsed})
    if ids != set(dataset):
        raise InvalidResult(f"{path.name}: el manifiesto no coincide con los casos canónicos.")
    order = {case_id: index for index, case_id in enumerate(dataset)}
    normalized.sort(key=lambda item: order[item["case_id"]])
    return {
        "source_file": _display_path(path),
        "sha256": _sha256(path),
        "run": {
            "variant": variant,
            "evaluated_at": evaluated_at,
            "provider": provider["provider"],
            "model": provider["model"],
            "judge_id": provider["judge_id"],
            "pf_worker_count": worker_count,
        },
        "rows": normalized,
    }


def load_result(path: Path, thresholds: dict[str, Any]) -> list[dict[str, Any]]:
    """Compatibilidad: carga filas normalizadas usando el manifiesto canónico."""

    validated = validate_thresholds(thresholds)
    dataset = load_dataset(DEFAULT_DATASET, validated)
    return _load_result_document(path, validated, dataset)["rows"]


def _failure_message(record: dict[str, Any]) -> str:
    if record["scope"] == "case":
        if record["rule"] == "equals":
            return f"{record['case_id']}: {record['metric']}={record['observed']:.0f}"
        return (
            f"{record['case_id']}: {record['metric']}={record['observed']:.2f} "
            f"< {record['expected']:.2f}"
        )
    return (
        f"{record['segment']}: promedio {record['metric']}={record['observed']:.2f} "
        f"< {record['expected']:.2f}"
    )


def _assess_policy(
    rows: list[dict[str, Any]],
    thresholds: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for row in rows:
        case = contract["cases"][row["case_id"]]
        required_binary = [
            metric for metric in _blocking_metrics(row["segment"], thresholds) if metric in BINARY_SCORES
        ]
        for metric in required_binary:
            if row["scores"][metric] != 1.0:
                records.append(
                    {
                        "scope": "case",
                        "case_id": row["case_id"],
                        "segment": row["segment"],
                        "failure_mode": case["failure_mode"],
                        "metric": metric,
                        "evaluator": contract["evaluators"][metric]["implementation"],
                        "rule": "equals",
                        "observed": row["scores"][metric],
                        "expected": 1.0,
                    }
                )
        if row["segment"] == "answerable":
            for metric in REQUIRED_JUDGE_SCORES:
                minimum = float(thresholds["answerable"][f"{metric}_row_min"])
                if row["scores"][metric] < minimum:
                    records.append(
                        {
                            "scope": "case",
                            "case_id": row["case_id"],
                            "segment": row["segment"],
                            "failure_mode": case["failure_mode"],
                            "metric": metric,
                            "evaluator": contract["evaluators"][metric]["implementation"],
                            "rule": "minimum",
                            "observed": row["scores"][metric],
                            "expected": minimum,
                        }
                    )

    answerable = [row for row in rows if row["segment"] == "answerable"]
    for metric in REQUIRED_JUDGE_SCORES:
        observed = mean(row["scores"][metric] for row in answerable)
        minimum = float(thresholds["answerable"][f"{metric}_average_min"])
        if observed < minimum:
            records.append(
                {
                    "scope": "segment",
                    "case_id": None,
                    "segment": "answerable",
                    "failure_mode": "answerable_segment_quality_regression",
                    "metric": metric,
                    "evaluator": contract["evaluators"][metric]["implementation"],
                    "rule": "average_minimum",
                    "observed": observed,
                    "expected": minimum,
                }
            )

    case_outcomes: dict[str, dict[str, Any]] = {}
    for row in rows:
        violations = [record for record in records if record["case_id"] == row["case_id"]]
        case_outcomes[row["case_id"]] = {
            "passed": not violations,
            "violations": [_failure_message(record) for record in violations],
        }
    return {
        "passed": not records,
        "failure_records": records,
        "failures": [_failure_message(record) for record in records],
        "case_outcomes": case_outcomes,
    }


def _worst_rows(runs: list[dict[str, Any]], case_order: Iterable[str]) -> list[dict[str, Any]]:
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        for row in run["rows"]:
            by_case[row["case_id"]].append(row)
    return [
        {
            "case_id": case_id,
            "segment": by_case[case_id][0]["segment"],
            "scores": {
                metric: min(observation["scores"][metric] for observation in by_case[case_id])
                for metric in ALL_SCORES
            },
        }
        for case_id in case_order
    ]


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _stability_analysis(
    runs: list[dict[str, Any]],
    case_order: Iterable[str],
    thresholds: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    case_order = list(case_order)
    judges = [run["run"]["judge_id"] for run in runs]
    if len(runs) == 1:
        comparison_mode = "single_run_only"
        mode_note = "Una sola corrida no permite medir estabilidad entre ejecuciones."
    elif len(set(judges)) == 1:
        comparison_mode = "repeatability_same_judge"
        mode_note = "Las corridas usan el mismo juez; las diferencias miden repetibilidad del scorer."
    else:
        comparison_mode = "cross_judge_robustness"
        mode_note = (
            "Las corridas usan jueces distintos; las diferencias miden robustez entre jueces, "
            "no repetibilidad pura."
        )

    rows_by_run = [{row["case_id"]: row for row in run["rows"]} for run in runs]
    metric_summaries: dict[str, dict[str, Any]] = {}
    by_case: list[dict[str, Any]] = []
    for case_id in case_order:
        metrics: dict[str, Any] = {}
        for metric in ALL_SCORES:
            values = [rows[case_id]["scores"][metric] for rows in rows_by_run]
            metrics[metric] = {
                "values": values,
                "minimum": min(values),
                "maximum": max(values),
                "range": round(max(values) - min(values), 4),
                "exact_agreement": len(set(values)) == 1,
            }
        by_case.append({"case_id": case_id, "metrics": metrics})

    for metric in ALL_SCORES:
        deltas: list[float] = []
        for case in by_case:
            values = case["metrics"][metric]["values"]
            deltas.extend(abs(left - right) for left, right in combinations(values, 2))
        exact = sum(delta == 0 for delta in deltas)
        summary: dict[str, Any] = {
            "pairwise_comparisons": len(deltas),
            "exact_agreement_rate": _rate(exact, len(deltas)),
            "mean_absolute_delta": round(mean(deltas), 4) if deltas else None,
            "maximum_absolute_delta": max(deltas) if deltas else None,
            "cases_with_variation": [
                case["case_id"] for case in by_case if case["metrics"][metric]["range"] > 0
            ],
        }
        if metric in REQUIRED_JUDGE_SCORES:
            summary["within_one_point_rate"] = _rate(sum(delta <= 1.0 for delta in deltas), len(deltas))
        else:
            summary["binary_flip_count"] = sum(delta == 1.0 for delta in deltas)
        metric_summaries[metric] = summary

    decisions = []
    for run in runs:
        assessed = _assess_policy(run["rows"], thresholds, contract)
        decisions.append(
            {
                "source_file": run["source_file"],
                "judge_id": run["run"]["judge_id"],
                "passed": assessed["passed"],
                "failure_count": len(assessed["failure_records"]),
            }
        )
    return {
        "run_count": len(runs),
        "comparison_mode": comparison_mode,
        "repeatability_claim_allowed": comparison_mode == "repeatability_same_judge",
        "note": mode_note,
        "gate_decision_agreement": len({decision["passed"] for decision in decisions}) == 1,
        "per_run_gate_decisions": decisions,
        "metrics": metric_summaries,
        "cases": by_case,
    }


def _wilson_interval(successes: int, sample_size: int, z: float = Z_95) -> tuple[float, float]:
    if sample_size <= 0 or not 0 <= successes <= sample_size:
        raise InvalidResult("No se puede calcular Wilson con conteos inválidos.")
    proportion = successes / sample_size
    denominator = 1.0 + z * z / sample_size
    center = (proportion + z * z / (2.0 * sample_size)) / denominator
    margin = z * math.sqrt(
        proportion * (1.0 - proportion) / sample_size + z * z / (4.0 * sample_size * sample_size)
    ) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def _minimum_all_success_sample(target_lower_bound: float) -> int:
    sample_size = 1
    while _wilson_interval(sample_size, sample_size)[0] < target_lower_bound:
        sample_size += 1
    return sample_size


def _sample_confidence(
    worst_rows: list[dict[str, Any]],
    case_outcomes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    target_lower_bound = 0.90
    minimum_target = _minimum_all_success_sample(target_lower_bound)

    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        sample_size = len(rows)
        successes = sum(case_outcomes[row["case_id"]]["passed"] for row in rows)
        lower, upper = _wilson_interval(successes, sample_size)
        return {
            "cases": sample_size,
            "conforming_cases": successes,
            "observed_rate": round(successes / sample_size, 4),
            "wilson_95_interval": {"lower": round(lower, 4), "upper": round(upper, 4)},
            "interval_width": round(upper - lower, 4),
            "additional_all_conforming_cases_to_0_90_lower_bound": max(0, minimum_target - sample_size),
        }

    overall = summarize(worst_rows)
    segments = {
        segment: summarize([row for row in worst_rows if row["segment"] == segment])
        for segment in SEGMENTS
    }
    return {
        "dataset_design": "fixed_curated_non_random",
        "population_inference_allowed": False,
        "method": "Wilson score interval, two-sided 95%, over case-level blocking conformance",
        "overall": overall,
        "segments": segments,
        "planning_heuristic": {
            "target_wilson_lower_bound": target_lower_bound,
            "minimum_all_conforming_cases_per_segment": minimum_target,
            "recommended_cases_per_segment": "35 mínimo; 50 preferible para calibración y subsegmentos",
        },
        "limitations": [
            "Los seis casos son fijos, curados y no aleatorios; el intervalo es descriptivo y no generaliza a producción.",
            "Las corridas repiten las mismas respuestas; no incrementan el tamaño muestral de seis casos.",
            "La cobertura de 1 a 3 casos por segmento no estima colas raras, idiomas, dominios ni ataques no representados.",
        ],
    }


def _traceability(
    worst_rows: list[dict[str, Any]],
    policy: dict[str, Any],
    thresholds: dict[str, Any],
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    for row in worst_rows:
        case = contract["cases"][row["case_id"]]
        blockers = set(_blocking_metrics(row["segment"], thresholds))
        evaluators = []
        for metric in case["evaluators"]:
            evaluator = contract["evaluators"][metric]
            rule: dict[str, Any] | None = None
            if metric in blockers and metric in BINARY_SCORES:
                rule = {"equals": 1.0}
            elif metric in blockers and row["segment"] == "answerable":
                rule = {
                    "row_min": float(thresholds["answerable"][f"{metric}_row_min"]),
                    "segment_average_min": float(
                        thresholds["answerable"][f"{metric}_average_min"]
                    ),
                }
            evaluators.append(
                {
                    "metric": metric,
                    "kind": evaluator["kind"],
                    "implementation": evaluator["implementation"],
                    "disposition": "blocking" if metric in blockers else "diagnostic",
                    "rule": rule,
                    "worst_observed": row["scores"][metric],
                }
            )
        outcome = policy["case_outcomes"][row["case_id"]]
        trace.append(
            {
                "case_id": row["case_id"],
                "segment": row["segment"],
                "expected_behavior": case["expected_behavior"],
                "failure_mode": case["failure_mode"],
                "risk": case["risk"],
                "evaluators": evaluators,
                "passed": outcome["passed"],
                "violations": outcome["violations"],
            }
        )
    return trace


def evaluate_gate(
    result_paths: list[Path],
    thresholds_path: Path = DEFAULT_THRESHOLDS,
    dataset_path: Path = DEFAULT_DATASET,
    contract_path: Path = DEFAULT_CONTRACT,
) -> dict[str, Any]:
    if not result_paths:
        raise InvalidResult("Debe proporcionarse al menos un archivo de resultados.")
    resolved_paths = [path.resolve() for path in result_paths]
    if len(resolved_paths) != len(set(resolved_paths)):
        raise InvalidResult("Cada corrida debe usar un archivo de resultados distinto.")

    thresholds_path = thresholds_path.resolve()
    dataset_path = dataset_path.resolve()
    contract_path = contract_path.resolve()
    thresholds = validate_thresholds(_read_json_object(thresholds_path, thresholds_path.name))
    dataset = load_dataset(dataset_path, thresholds)
    contract = load_quality_contract(contract_path, dataset, thresholds)
    runs = [_load_result_document(path, thresholds, dataset) for path in resolved_paths]
    variants = {run["run"]["variant"] for run in runs}
    if len(variants) != 1:
        raise InvalidResult("Las corridas no evalúan la misma variant; no se pueden agregar.")

    worst_rows = _worst_rows(runs, dataset)
    policy = _assess_policy(worst_rows, thresholds, contract)
    segments: dict[str, dict[str, float]] = {}
    for segment in SEGMENTS:
        segment_rows = [row for row in worst_rows if row["segment"] == segment]
        segments[segment] = {
            metric: round(mean(row["scores"][metric] for row in segment_rows), 4)
            for metric in ALL_SCORES
        }

    traceability = _traceability(worst_rows, policy, thresholds, contract)
    stability = _stability_analysis(runs, dataset, thresholds, contract)
    confidence = _sample_confidence(worst_rows, policy["case_outcomes"])
    passed = policy["passed"]
    return {
        "schema_version": "1.0",
        "analysis_version": ANALYSIS_VERSION,
        "status": "passed" if passed else "failed",
        "passed": passed,
        "release_decision": "PASS_FIXED_DATASET_GATE" if passed else "BLOCK_QUALITY_GATE",
        "release_scope": "Solo el dataset fijo y la política versionada; no certifica producción.",
        "runs_evaluated": len(runs),
        "variant": next(iter(variants)),
        "aggregation": "worst score per case across runs",
        "failures": policy["failures"],
        "failure_records": policy["failure_records"],
        "segment_metrics": segments,
        "cases": [
            {
                **row,
                "passed": policy["case_outcomes"][row["case_id"]]["passed"],
                "violations": policy["case_outcomes"][row["case_id"]]["violations"],
            }
            for row in worst_rows
        ],
        "traceability": traceability,
        "stability": stability,
        "sample_confidence": confidence,
        "evidence": {
            "thresholds": {
                "source_file": _display_path(thresholds_path),
                "sha256": _sha256(thresholds_path),
            },
            "dataset": {"source_file": _display_path(dataset_path), "sha256": _sha256(dataset_path)},
            "quality_contract": {
                "source_file": _display_path(contract_path),
                "sha256": _sha256(contract_path),
            },
            "runs": [
                {"source_file": run["source_file"], "sha256": run["sha256"], **run["run"]}
                for run in runs
            ],
        },
        "limitations": [
            "El PASS conserva el peor score por caso, pero solo cubre seis respuestas sembradas.",
            stability["note"],
            "Groundedness y Relevance son diagnósticos para no-respondibles; abstención y consistencia son bloqueantes.",
            "Los controles de riesgo no ejecutados no se convierten en métricas ni en cobertura implícita.",
        ],
    }


def _md_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict[str, Any]) -> str:
    """Genera un informe legible a partir del mismo objeto usado por automatización."""

    if report.get("status") == "invalid":
        lines = [
            "# Quality gate de IA",
            "",
            "**Decisión: BLOCK_INVALID_EVIDENCE**",
            "",
            "La evidencia no cumple el contrato fail-closed:",
            "",
        ]
        lines.extend(f"- {_md_cell(error)}" for error in report.get("errors", []))
        return "\n".join(lines) + "\n"

    lines = [
        "# Quality gate de IA",
        "",
        f"**Decisión:** `{report['release_decision']}`  ",
        f"**Estado:** `{report['status']}` · **Corridas:** {report['runs_evaluated']} · "
        f"**Agregación:** {report['aggregation']}  ",
        f"**Alcance:** {report['release_scope']}",
        "",
        "## Evidencia e integridad",
        "",
        "| Corrida | Juez | Fecha UTC | SHA-256 |",
        "|---|---|---|---|",
    ]
    for run in report["evidence"]["runs"]:
        lines.append(
            f"| {_md_cell(run['source_file'])} | {_md_cell(run['judge_id'])} | "
            f"{_md_cell(run.get('evaluated_at') or 'fixture determinista')} | `{run['sha256'][:12]}…` |"
        )
    lines.extend(["", "## Incumplimientos", ""])
    if report["failures"]:
        lines.extend(f"- {failure}" for failure in report["failures"])
    else:
        lines.append("- Ninguno según los umbrales versionados.")

    lines.extend(
        [
            "",
            "## Trazabilidad caso → modo de fallo → evaluador",
            "",
            "| Caso | Segmento | Modo de fallo | Bloqueantes | Diagnósticos | Resultado |",
            "|---|---|---|---|---|---|",
        ]
    )
    for case in report["traceability"]:
        blocking = ", ".join(
            evaluator["metric"] for evaluator in case["evaluators"] if evaluator["disposition"] == "blocking"
        )
        diagnostic = ", ".join(
            evaluator["metric"]
            for evaluator in case["evaluators"]
            if evaluator["disposition"] == "diagnostic"
        ) or "—"
        lines.append(
            f"| {case['case_id']} | {case['segment']} | {_md_cell(case['failure_mode'])} | "
            f"{_md_cell(blocking)} | {_md_cell(diagnostic)} | {'PASS' if case['passed'] else 'FAIL'} |"
        )

    stability = report["stability"]
    lines.extend(
        [
            "",
            "## Estabilidad entre corridas",
            "",
            f"**Modo:** `{stability['comparison_mode']}`. {stability['note']}",
            "",
            "| Métrica | Comparaciones | Acuerdo exacto | Delta medio | Delta máximo | Casos variables |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for metric, values in stability["metrics"].items():
        exact = values["exact_agreement_rate"]
        lines.append(
            f"| {metric} | {values['pairwise_comparisons']} | "
            f"{('N/A' if exact is None else f'{exact:.1%}')} | "
            f"{('N/A' if values['mean_absolute_delta'] is None else values['mean_absolute_delta'])} | "
            f"{('N/A' if values['maximum_absolute_delta'] is None else values['maximum_absolute_delta'])} | "
            f"{_md_cell(', '.join(values['cases_with_variation']) or '—')} |"
        )

    confidence = report["sample_confidence"]
    lines.extend(
        [
            "",
            "## Confianza muestral descriptiva",
            "",
            "| Segmento | Casos conformes / n | Tasa observada | Wilson 95% | Faltan para n=35 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    confidence_rows = {"overall": confidence["overall"], **confidence["segments"]}
    for segment, values in confidence_rows.items():
        interval = values["wilson_95_interval"]
        lines.append(
            f"| {segment} | {values['conforming_cases']} / {values['cases']} | "
            f"{values['observed_rate']:.1%} | [{interval['lower']:.1%}, {interval['upper']:.1%}] | "
            f"{values['additional_all_conforming_cases_to_0_90_lower_bound']} |"
        )
    lines.extend(["", "**Lectura obligatoria:** " + confidence["limitations"][0], "", "## Limitaciones", ""])
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _write_report(path: Path | None, report: dict[str, Any]) -> None:
    if path:
        _atomic_write(path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")


def _default_markdown_path(json_path: Path | None) -> Path | None:
    if json_path is None:
        return None
    return json_path.with_suffix(".md") if json_path.suffix.lower() == ".json" else Path(f"{json_path}.md")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, nargs="+", required=True)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, help="Reporte JSON machine-readable.")
    parser.add_argument("--report-md", type=Path, help="Reporte Markdown human-readable.")
    args = parser.parse_args(argv)
    markdown_path = args.report_md or _default_markdown_path(args.report)
    if args.report and markdown_path and args.report.resolve() == markdown_path.resolve():
        parser.error("--report y --report-md deben ser archivos distintos.")
    try:
        report = evaluate_gate(
            [path.resolve() for path in args.results],
            args.thresholds.resolve(),
            args.dataset.resolve(),
            args.contract.resolve(),
        )
    except InvalidResult as exc:
        report = {
            "schema_version": "1.0",
            "analysis_version": ANALYSIS_VERSION,
            "status": "invalid",
            "passed": False,
            "release_decision": "BLOCK_INVALID_EVIDENCE",
            "errors": [str(exc)],
        }
        _write_report(args.report, report)
        if markdown_path:
            _atomic_write(markdown_path, render_markdown(report))
        print(json.dumps(report, ensure_ascii=False))
        return 2
    _write_report(args.report, report)
    if markdown_path:
        _atomic_write(markdown_path, render_markdown(report))
    print(
        json.dumps(
            {
                "status": report["status"],
                "release_decision": report["release_decision"],
                "failures": report["failures"],
                "comparison_mode": report["stability"]["comparison_mode"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
