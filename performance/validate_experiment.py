"""Gate fail-closed para la validez del experimento de rendimiento.

No confunde dos decisiones distintas:

* ``service_gate`` comprueba que un smoke sano cumple su SLO laxo.
* ``experiment_gate`` comprueba que una rampa diagnóstica alcanzó la carga,
  cruzó los umbrales y expuso los dos factores limitantes buscados.

Códigos: 0=aprobado, 1=política incumplida, 2=evidencia/configuración inválida.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


class InvalidEvidence(ValueError):
    """La evidencia no permite tomar una decisión confiable."""


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidEvidence(f"{label} debe ser un objeto")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidEvidence(f"{label} debe ser numérico")
    result = float(value)
    if not math.isfinite(result):
        raise InvalidEvidence(f"{label} debe ser finito")
    return result


def _required_observation(history: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = history.get(key)
    if value is None:
        return None
    return _object(value, f"history.{key}")


def validate_summary(summary: dict[str, Any], policy_document: dict[str, Any]) -> dict[str, Any]:
    if summary.get("executed") is not True:
        raise InvalidEvidence("summary.executed debe ser true")
    profile = summary.get("profile")
    if not isinstance(profile, str) or not profile:
        raise InvalidEvidence("summary.profile es obligatorio")
    policies = _object(policy_document.get("profiles"), "policy.profiles")
    policy = _object(policies.get(profile), f"policy.profiles.{profile}")
    aggregate = _object(summary.get("aggregate"), "summary.aggregate")
    history = _object(summary.get("history"), "summary.history")
    if history.get("available") is not True:
        raise InvalidEvidence("summary.history no está disponible")

    failures: list[str] = []
    requests = _number(aggregate.get("requests"), "aggregate.requests")
    error = _number(aggregate.get("error_percentage"), "aggregate.error_percentage")
    p95 = _number(aggregate.get("p95_ms"), "aggregate.p95_ms")
    max_users = _number(history.get("max_users"), "history.max_users")

    if requests < _number(policy.get("minimum_requests"), "policy.minimum_requests"):
        failures.append("solicitudes insuficientes para validar el perfil")
    if max_users != _number(policy.get("expected_max_users"), "policy.expected_max_users"):
        failures.append("no se alcanzó exactamente la carga máxima prevista")

    mode = policy.get("mode")
    if mode == "service_gate":
        if error > _number(policy.get("maximum_error_percentage"), "policy.maximum_error_percentage"):
            failures.append("porcentaje de error por encima del SLO del smoke")
        if p95 > _number(policy.get("maximum_p95_ms"), "policy.maximum_p95_ms"):
            failures.append("p95 por encima del SLO del smoke")
    elif mode == "experiment_gate":
        p95_crossing = _required_observation(history, "first_p95_above_5000_ms")
        error_crossing = _required_observation(history, "first_error_above_5_percent")
        rate_limit = _required_observation(history, "first_failure")
        if policy.get("require_p95_above_5000") is True and p95_crossing is None:
            failures.append("la prueba no cruzó p95 > 5 000 ms")
        if policy.get("require_error_above_5_percent") is True and error_crossing is None:
            failures.append("la prueba no cruzó error acumulado > 5%")
        if policy.get("require_rate_limit") is True and rate_limit is None:
            failures.append("la prueba no produjo el régimen de 429")
        if rate_limit is not None:
            users = _number(rate_limit.get("users"), "history.first_failure.users")
            if users < _number(policy.get("first_rate_limit_users_min"), "policy.first_rate_limit_users_min"):
                failures.append("el 429 apareció antes de la carga mínima diseñada")
        success_rps = _number(
            history.get("peak_success_requests_per_second"),
            "history.peak_success_requests_per_second",
        )
        lower = _number(policy.get("successful_rps_min"), "policy.successful_rps_min")
        upper = _number(policy.get("successful_rps_max"), "policy.successful_rps_max")
        if not lower <= success_rps <= upper:
            failures.append("throughput exitoso fuera del rango del modelo analítico")
    else:
        raise InvalidEvidence(f"modo de política desconocido: {mode!r}")

    return {
        "schema_version": "1.0",
        "status": "passed" if not failures else "failed",
        "passed": not failures,
        "profile": profile,
        "mode": mode,
        "failures": failures,
        "observed": {
            "requests": int(requests),
            "max_users": int(max_users),
            "error_percentage": error,
            "p95_ms": p95,
            "peak_success_requests_per_second": history.get(
                "peak_success_requests_per_second"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path(__file__).with_name("experiment_policy.json"),
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        summary = json.loads(args.summary.read_text(encoding="utf-8"))
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        result = validate_summary(_object(summary, "summary"), _object(policy, "policy"))
        exit_code = 0 if result["passed"] else 1
    except (OSError, json.JSONDecodeError, InvalidEvidence) as exc:
        result = {
            "schema_version": "1.0",
            "status": "invalid",
            "passed": False,
            "failures": [str(exc)],
        }
        exit_code = 2
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    print(serialized, end="")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized, encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
