"""Resume los CSV que genera Locust sin dependencias adicionales."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _number(row: dict[str, str], *keys: str) -> float:
    for key in keys:
        value = row.get(key, "")
        if value not in ("", None):
            return float(value)
    raise KeyError(f"ninguna columna disponible: {keys}")


def _aggregate(stats_path: Path) -> dict[str, Any]:
    with stats_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    row = next((item for item in rows if item.get("Name") == "Aggregated"), None)
    if row is None:
        raise ValueError(f"{stats_path} no contiene la fila Aggregated")
    requests = int(_number(row, "Request Count"))
    failures = int(_number(row, "Failure Count"))
    return {
        "requests": requests,
        "failures": failures,
        "error_percentage": round((failures / requests * 100) if requests else 0.0, 3),
        "requests_per_second": round(_number(row, "Requests/s"), 3),
        "failures_per_second": round(_number(row, "Failures/s"), 3),
        "average_ms": round(_number(row, "Average Response Time"), 3),
        "minimum_ms": round(_number(row, "Min Response Time"), 3),
        "maximum_ms": round(_number(row, "Max Response Time"), 3),
        "p50_ms": round(_number(row, "50%", "Median Response Time"), 3),
        "p95_ms": round(_number(row, "95%"), 3),
        "p99_ms": round(_number(row, "99%"), 3),
    }


def _history(history_path: Path, profile: str) -> dict[str, Any]:
    if not history_path.exists():
        return {"available": False}
    with history_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row.get("Name") == "Aggregated"]
    if not rows:
        return {"available": False}
    def numeric(row: dict[str, str], key: str, default: float = 0.0) -> float:
        raw = row.get(key)
        if raw in (None, "", "N/A"):
            return default
        return float(raw)

    active = [row for row in rows if int(numeric(row, "User Count")) > 0]
    first_timestamp = int(numeric(rows[0], "Timestamp"))
    first_failure_row = next(
        (row for row in rows if numeric(row, "Total Failure Count") > 0),
        None,
    )
    first_error_threshold_row = next(
        (
            row
            for row in rows
            if numeric(row, "Total Request Count") > 0
            and numeric(row, "Total Failure Count") / numeric(row, "Total Request Count") * 100 > 5
        ),
        None,
    )
    first_slo_row = next((row for row in active if numeric(row, "95%") > 5000), None)
    p95_values = [numeric(row, "95%") for row in active if row.get("95%") not in (None, "", "N/A")]
    first_sample_p95 = p95_values[0] if p95_values else None
    peak_attempt = max((numeric(row, "Requests/s") for row in active), default=0.0)
    peak_success = max(
        (numeric(row, "Requests/s") - numeric(row, "Failures/s") for row in active),
        default=0.0,
    )

    def observation(row: dict[str, str] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        timestamp = int(numeric(row, "Timestamp"))
        return {
            "timestamp": timestamp,
            "elapsed_seconds": timestamp - first_timestamp,
            "users": int(numeric(row, "User Count")),
            "p95_ms": numeric(row, "95%"),
            "total_requests": int(numeric(row, "Total Request Count")),
            "total_failures": int(numeric(row, "Total Failure Count")),
        }

    stage_peaks: list[dict[str, Any]] = []
    for target in (1, 2, 4, 6, 10, 20, 40, 60):
        stage_rows = [row for row in active if int(numeric(row, "User Count")) == target]
        if not stage_rows:
            continue
        last = stage_rows[-1]
        valid_p95 = [numeric(row, "95%") for row in stage_rows if row.get("95%") not in (None, "", "N/A")]
        error_rates = [
            (
                numeric(row, "Total Failure Count") / numeric(row, "Total Request Count") * 100
                if numeric(row, "Total Request Count")
                else 0.0
            )
            for row in stage_rows
        ]
        stage_peaks.append(
            {
                "users": target,
                "samples": len(stage_rows),
                "last_p95_ms": numeric(last, "95%") if last.get("95%") not in (None, "", "N/A") else None,
                "maximum_p95_ms": max(valid_p95) if valid_p95 else None,
                "last_average_ms": round(numeric(last, "Total Average Response Time"), 3),
                "peak_success_requests_per_second": round(
                    max(
                        numeric(row, "Requests/s") - numeric(row, "Failures/s")
                        for row in stage_rows
                    ),
                    3,
                ),
                "maximum_cumulative_error_percentage": round(max(error_rates), 3),
            }
        )

    # La rampa usa 4 VU como nivel estable de referencia: coincide con
    # MAX_CONC y tiene una etapa completa de 60 s. La primera muestra de 1 VU
    # aún está calentando el proceso y no es una base defendible para afirmar
    # una degradación 2x. En perfiles sin etapas estables (control/smoke), esta
    # comparación no se calcula.
    reference_users = (
        4
        if profile == "saturation" and any(stage["users"] == 4 for stage in stage_peaks)
        else None
    )
    reference_rows = (
        [row for row in active if int(numeric(row, "User Count")) == reference_users]
        if reference_users is not None
        else []
    )
    reference_tail = [
        numeric(row, "95%")
        for row in reference_rows[-30:]
        if row.get("95%") not in (None, "", "N/A")
    ]
    reference_p95 = statistics.median(reference_tail) if reference_tail else None
    first_double_reference_row = next(
        (
            row
            for row in active
            if reference_users is not None
            and reference_p95 is not None
            and int(numeric(row, "User Count")) >= reference_users
            and row.get("95%") not in (None, "", "N/A")
            and numeric(row, "95%") >= reference_p95 * 2
        ),
        None,
    )

    return {
        "available": True,
        "samples": len(rows),
        "max_users": max(int(numeric(row, "User Count")) for row in rows),
        "first_sample_p95_ms": first_sample_p95,
        "reference_baseline_users": reference_users,
        "reference_baseline_p95_ms": reference_p95,
        "reference_baseline_method": "median_last_30_samples" if reference_tail else None,
        "maximum_p95_ms": max(p95_values) if p95_values else None,
        "peak_attempt_requests_per_second": round(peak_attempt, 3),
        "peak_success_requests_per_second": round(peak_success, 3),
        "first_failure": observation(first_failure_row),
        "first_error_above_5_percent": observation(first_error_threshold_row),
        "first_p95_above_5000_ms": observation(first_slo_row),
        "first_p95_at_least_2x_reference_baseline": observation(first_double_reference_row),
        "stage_peaks": stage_peaks,
    }


def summarize(prefix: Path, profile: str) -> dict[str, Any]:
    stats_path = Path(f"{prefix}_stats.csv")
    summary = {
        "executed": True,
        "profile": profile,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_stats": stats_path.name,
        "aggregate": _aggregate(stats_path),
        "history": _history(Path(f"{prefix}_stats_history.csv"), profile),
    }
    return summary


def write_summary(prefix: Path, summary: dict[str, Any]) -> tuple[Path, Path]:
    json_path = prefix.parent / "summary.json"
    markdown_path = prefix.parent / "summary.md"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    aggregate = summary["aggregate"]
    history = summary["history"]
    lines = [
        "# Resumen de ejecución Locust",
        "",
        f"- Perfil: `{summary['profile']}`",
        f"- Generado (UTC): `{summary['generated_at_utc']}`",
        f"- Solicitudes: {aggregate['requests']}",
        f"- Fallos: {aggregate['failures']} ({aggregate['error_percentage']}%)",
        f"- Throughput intentado: {aggregate['requests_per_second']} req/s",
        f"- Latencia: p50={aggregate['p50_ms']} ms, p95={aggregate['p95_ms']} ms, p99={aggregate['p99_ms']} ms",
        f"- Rango: {aggregate['minimum_ms']} a {aggregate['maximum_ms']} ms",
    ]
    if history.get("available"):
        lines.extend(
            [
                f"- Máximo de usuarios observado: {history['max_users']}",
                f"- Primera muestra p95: {history['first_sample_p95_ms']} ms",
                f"- p95 máximo: {history['maximum_p95_ms']} ms",
                f"- Pico de throughput intentado/exitoso: {history['peak_attempt_requests_per_second']} / {history['peak_success_requests_per_second']} req/s",
                f"- Primer fallo: {history['first_failure']}",
                f"- Primer error acumulado >5%: {history['first_error_above_5_percent']}",
                f"- Primer p95 >5 000 ms: {history['first_p95_above_5000_ms']}",
            ]
        )
        if history.get("reference_baseline_p95_ms") is not None:
            lines.extend(
                [
                    f"- Baseline estable: {history['reference_baseline_p95_ms']} ms a {history['reference_baseline_users']} VU ({history['reference_baseline_method']})",
                    f"- Primer p95 >=2x baseline estable: {history['first_p95_at_least_2x_reference_baseline']}",
                ]
            )
        if summary["profile"] == "saturation":
            lines.extend(
                f"- Nivel {stage['users']} usuarios: p95 final={stage['last_p95_ms']} ms, "
                f"p95 máx={stage['maximum_p95_ms']} ms, éxito pico={stage['peak_success_requests_per_second']} req/s, "
                f"error acum. máx={stage['maximum_cumulative_error_percentage']}%"
                for stage in history["stage_peaks"]
            )
        else:
            lines.append(
                "- Nota: los cambios de User Count posteriores al fin pertenecen al drenaje; no se interpretan como niveles de carga."
            )
    lines.extend(
        [
            "",
            "Los 429 válidos cuentan como fallos de capacidad. La latencia agregada mezcla respuestas 200 encoladas con 429 rápidos; el porcentaje de error debe interpretarse junto con p95/p99.",
            "",
        ]
    )
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args()
    summary = summarize(args.prefix, args.profile)
    json_path, markdown_path = write_summary(args.prefix, summary)
    print(f"Resumen JSON: {json_path}")
    print(f"Resumen Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
