"""Gate estructural y de evidencia previo a una entrega.

Este control no reemplaza las pruebas de cada bloque. Verifica que el repositorio
que las contiene siga siendo evaluable, trazable y seguro. Código 0=aprobado,
1=incumplimiento, 2=error de ejecución/configuración.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = {
    "google_api_key": re.compile(r"AIza[A-Za-z0-9_-]{20,}"),
    "openai_api_key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "github_token": re.compile(r"(?:github_pat_|ghp_)[A-Za-z0-9_]{20,}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "credential_url": re.compile(r"https?://[^/\s:@]+:[^@\s/]+@"),
}


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def tracked_files(root: Path = ROOT) -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [root / item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]


def scan_secrets(paths: list[Path]) -> list[str]:
    findings: list[str] = []
    for path in paths:
        if path.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".zip"}:
            continue
        if path.name == "report.html" and "performance" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT).as_posix()}: {label}")
    return findings


def repository_checks(root: Path = ROOT) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    required = [
        "README.md",
        "IA.md",
        "AGENTS.md",
        ".github/workflows/ci.yml",
        ".github/workflows/toolshop-local.yml",
        "docs/informe-ejecutivo.pdf",
        "docs/senior-qa-strategy.md",
        "docs/traceability-matrix.md",
        "functional-api/pom.xml",
        "performance/config.yaml",
        "performance/experiment_manifest.json",
        "performance/experiment_policy.json",
        "evaluation/data/evaluation_cases.jsonl",
        "evaluation/results/quality_gate_good.json",
        "evaluation/results/quality_gate_negative_control.json",
        "evaluation/results/sdk_audit_same_judge_good_20260824T230559Z.json",
        "evaluation/results/sdk_audit_negative_control_bad_20260824T230741Z.json",
        "evaluation/risk_safety_factory.py",
    ]
    missing = [item for item in required if not (root / item).is_file()]
    record("required_deliverables", not missing, "missing=" + ",".join(missing) if missing else "complete")

    feature = (root / "functional-api/src/test/resources/toolshop/toolshop-api.feature").read_text(
        encoding="utf-8"
    )
    scenarios = re.findall(r"(?m)^\s*Scenario(?: Outline)?:", feature)
    record("functional_scenario_budget", len(scenarios) == 4, f"scenarios={len(scenarios)}")

    cases = [
        json.loads(line)
        for line in (root / "evaluation/data/evaluation_cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ids = [case.get("case_id") for case in cases]
    segments = {segment: sum(case.get("segment") == segment for case in cases) for segment in ("answerable", "unanswerable", "adversarial")}
    required_fields = {"case_id", "query", "context", "response", "segment"}
    dataset_ok = (
        len(cases) == 6
        and len(ids) == len(set(ids))
        and segments == {"answerable": 2, "unanswerable": 1, "adversarial": 3}
        and all(required_fields <= set(case) for case in cases)
    )
    record("evaluation_dataset_contract", dataset_ok, f"cases={len(cases)} segments={segments}")

    with (root / "performance/prompts.csv").open(encoding="utf-8-sig", newline="") as stream:
        prompts = list(csv.DictReader(stream))
    prompt_ok = len(prompts) == 12 and len({row.get("prompt") for row in prompts}) == 12
    record("performance_prompt_parameterization", prompt_ok, f"rows={len(prompts)} unique={len({row.get('prompt') for row in prompts})}")

    quality = _read_json(root / "evaluation/results/quality_gate_good.json")
    stability = quality.get("stability", {})
    record(
        "versioned_quality_gate",
        quality.get("status") == "passed"
        and quality.get("runs_evaluated", 0) >= 2
        and stability.get("comparison_mode") == "repeatability_same_judge"
        and stability.get("repeatability_claim_allowed") is True,
        (
            f"status={quality.get('status')} runs={quality.get('runs_evaluated')} "
            f"mode={stability.get('comparison_mode')}"
        ),
    )

    negative = _read_json(root / "evaluation/results/quality_gate_negative_control.json")
    record(
        "real_negative_control_blocks",
        negative.get("status") == "failed"
        and negative.get("variant") == "bad"
        and negative.get("release_decision") == "BLOCK_QUALITY_GATE"
        and len(negative.get("failures", [])) > 0,
        f"status={negative.get('status')} failures={len(negative.get('failures', []))}",
    )

    sdk_paths = [
        root / "evaluation/results/sdk_audit_same_judge_good_20260824T230559Z.json",
        root / "evaluation/results/sdk_audit_negative_control_bad_20260824T230741Z.json",
    ]
    sdk_evidence = [_read_json(path) for path in sdk_paths]
    sdk_serialized = "\n".join(path.read_text(encoding="utf-8") for path in sdk_paths)
    sdk_ok = (
        {item.get("run", {}).get("variant") for item in sdk_evidence} == {"good", "bad"}
        and all(item.get("evidence_type") == "sanitized_azure_ai_evaluation_sdk_output" for item in sdk_evidence)
        and all(len(item.get("rows", [])) == 6 for item in sdk_evidence)
        and "sample_input" not in sdk_serialized
        and "sample_output" not in sdk_serialized
    )
    record("sanitized_sdk_evidence", sdk_ok, "good+bad; 6 rows each; prompts removed")

    load_profiles = {
        "smoke": root / "performance/results/smoke-20260824-170904/summary.json",
        "saturation": root / "performance/results/saturation-20260824-171114/summary.json",
        "control": root / "performance/results/control-20260824-172019/summary.json",
    }
    load_ok = all(
        path.is_file()
        and _read_json(path).get("executed") is True
        and _read_json(path).get("profile") == profile
        for profile, path in load_profiles.items()
    )
    record("load_evidence_profiles", load_ok, "smoke+saturation+control")

    experiment_gates = [
        root / "performance/results/smoke-20260824-170904/experiment-gate.json",
        root / "performance/results/saturation-20260824-171114/experiment-gate.json",
        root / "performance/results/control-20260824-172019/experiment-gate.json",
    ]
    experiment_gate_ok = all(
        path.is_file() and _read_json(path).get("passed") is True
        for path in experiment_gates
    )
    record("load_profile_gates", experiment_gate_ok, "service+experiment gates passed")

    azure_config = (root / "performance/config.yaml").read_text(encoding="utf-8")
    record(
        "azure_load_target_is_runtime_injected",
        "TARGET_HOST" not in azure_config and "127.0.0.1" not in azure_config,
        "no loopback target embedded",
    )

    run_status = _read_json(root / "evaluation/results/run_status.json")
    referenced: list[str] = []
    for run in run_status.get("runs", []):
        referenced.extend(run[key] for key in ("result", "sdk_audit") if key in run)
    referenced.extend(
        gate["report"]
        for gate in run_status.get("quality_gates", {}).values()
        if "report" in gate
    )
    broken = [name for name in referenced if not (root / "evaluation/results" / name).is_file()]
    record("evaluation_references_resolve", not broken, "complete" if not broken else ",".join(broken))

    pdf_size = (root / "docs/informe-ejecutivo.pdf").stat().st_size
    record("report_not_empty", pdf_size > 50_000, f"bytes={pdf_size}")

    tracked = tracked_files(root)
    tracked_names = {path.relative_to(root).as_posix() for path in tracked}
    forbidden = sorted(
        name
        for name in tracked_names
        if name == ".env" or name.startswith(".venv/") or "/target/" in f"/{name}/"
    )
    record("forbidden_files_not_tracked", not forbidden, "clean" if not forbidden else ",".join(forbidden))

    secret_findings = scan_secrets(tracked)
    record("tracked_secret_scan", not secret_findings, "0 findings" if not secret_findings else "; ".join(secret_findings))
    return checks


def build_report(root: Path = ROOT) -> dict[str, object]:
    checks = repository_checks(root)
    return {
        "schema_version": "1.0",
        "status": "passed" if all(check["passed"] for check in checks) else "failed",
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = build_report()
        exit_code = 0 if report["passed"] else 1
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        report = {
            "schema_version": "1.0",
            "status": "invalid",
            "passed": False,
            "checks": [],
            "error": str(exc),
        }
        exit_code = 2
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(serialized, end="")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized, encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
