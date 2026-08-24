"""Quality gate fail-closed. Códigos: 0 aprobado, 1 calidad insuficiente, 2 entrada inválida."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parent
REQUIRED_JUDGE_SCORES = ("groundedness", "relevance")
ALL_SCORES = REQUIRED_JUDGE_SCORES + (
    "price_consistency",
    "abstention",
    "injection_resistance",
)


class InvalidResult(ValueError):
    pass


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise InvalidResult(f"{label} no es un número finito.")
    return float(value)


def load_result(path: Path, thresholds: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidResult(f"No se pudo leer {path}: {exc}") from exc
    if payload.get("schema_version") != "1.0" or payload.get("run", {}).get("status") != "completed":
        raise InvalidResult(f"{path.name}: esquema o estado de ejecución inválido.")
    rows = payload.get("rows")
    expected_count = int(thresholds["expected_case_count"])
    if not isinstance(rows, list) or len(rows) != expected_count:
        raise InvalidResult(f"{path.name}: se esperaban {expected_count} filas completas.")
    ids: set[str] = set()
    counts: Counter[str] = Counter()
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise InvalidResult(f"{path.name}: fila {index} no es un objeto.")
        case_id = str(row.get("case_id", "")).strip()
        segment = str(row.get("segment", "")).strip()
        scores = row.get("scores")
        if not case_id or case_id in ids:
            raise InvalidResult(f"{path.name}: case_id vacío o duplicado: {case_id!r}.")
        if segment not in thresholds["expected_segment_counts"]:
            raise InvalidResult(f"{path.name}: segmento inválido en {case_id}: {segment!r}.")
        if not isinstance(scores, dict):
            raise InvalidResult(f"{path.name}: scores ausente en {case_id}.")
        parsed = {name: _number(scores.get(name), f"{case_id}.{name}") for name in ALL_SCORES}
        for name in REQUIRED_JUDGE_SCORES:
            if not 1.0 <= parsed[name] <= 5.0:
                raise InvalidResult(f"{case_id}.{name} debe estar entre 1 y 5.")
        for name in ALL_SCORES[2:]:
            if parsed[name] not in {0.0, 1.0}:
                raise InvalidResult(f"{case_id}.{name} debe ser binario (0/1).")
        ids.add(case_id)
        counts[segment] += 1
        normalized.append({"case_id": case_id, "segment": segment, "scores": parsed})
    expected_segments = Counter({key: int(value) for key, value in thresholds["expected_segment_counts"].items()})
    if counts != expected_segments:
        raise InvalidResult(f"{path.name}: distribución {dict(counts)}; esperada {dict(expected_segments)}.")
    return normalized


def evaluate_gate(result_paths: list[Path], thresholds_path: Path) -> dict[str, Any]:
    if not result_paths:
        raise InvalidResult("Debe proporcionarse al menos un archivo de resultados.")
    try:
        thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        raise InvalidResult(f"Thresholds inválidos: {exc}") from exc
    runs = [load_result(path, thresholds) for path in result_paths]
    first_manifest = {(row["case_id"], row["segment"]) for row in runs[0]}
    for index, run_rows in enumerate(runs[1:], start=2):
        manifest = {(row["case_id"], row["segment"]) for row in run_rows}
        if manifest != first_manifest:
            raise InvalidResult(f"La corrida {index} no contiene el mismo manifiesto de casos.")

    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run_rows in runs:
        for row in run_rows:
            by_case[row["case_id"]].append(row)
    worst_rows: list[dict[str, Any]] = []
    for case_id, observations in sorted(by_case.items()):
        worst_rows.append(
            {
                "case_id": case_id,
                "segment": observations[0]["segment"],
                "scores": {name: min(item["scores"][name] for item in observations) for name in ALL_SCORES},
            }
        )

    failures: list[str] = []
    required_binary = thresholds["required_binary_scores"]
    for row in worst_rows:
        required = list(required_binary.get("all", [])) + list(required_binary.get(row["segment"], []))
        for metric in required:
            if row["scores"][metric] != 1.0:
                failures.append(f"{row['case_id']}: {metric}=0")

    answerable = [row for row in worst_rows if row["segment"] == "answerable"]
    answer_thresholds = thresholds["answerable"]
    for metric in REQUIRED_JUDGE_SCORES:
        row_min = float(answer_thresholds[f"{metric}_row_min"])
        average_min = float(answer_thresholds[f"{metric}_average_min"])
        for row in answerable:
            if row["scores"][metric] < row_min:
                failures.append(f"{row['case_id']}: {metric}={row['scores'][metric]:.2f} < {row_min:.2f}")
        average = mean(row["scores"][metric] for row in answerable)
        if average < average_min:
            failures.append(f"answerable: promedio {metric}={average:.2f} < {average_min:.2f}")

    segments: dict[str, dict[str, float]] = {}
    for segment in thresholds["expected_segment_counts"]:
        segment_rows = [row for row in worst_rows if row["segment"] == segment]
        segments[segment] = {
            metric: round(mean(row["scores"][metric] for row in segment_rows), 4) for metric in ALL_SCORES
        }
    return {
        "schema_version": "1.0",
        "status": "passed" if not failures else "failed",
        "passed": not failures,
        "runs_evaluated": len(runs),
        "aggregation": "worst score per case across runs",
        "failures": failures,
        "segment_metrics": segments,
        "cases": worst_rows,
    }


def _write_report(path: Path | None, report: dict[str, Any]) -> None:
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, nargs="+", required=True)
    parser.add_argument("--thresholds", type=Path, default=ROOT / "thresholds.json")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        report = evaluate_gate([path.resolve() for path in args.results], args.thresholds.resolve())
    except InvalidResult as exc:
        report = {"schema_version": "1.0", "status": "invalid", "passed": False, "errors": [str(exc)]}
        _write_report(args.report, report)
        print(json.dumps(report, ensure_ascii=False))
        return 2
    _write_report(args.report, report)
    print(json.dumps({"status": report["status"], "failures": report["failures"]}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
