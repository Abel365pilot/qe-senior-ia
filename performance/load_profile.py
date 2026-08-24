"""Funciones puras de datos y perfiles para probar Locust sin monkey-patching."""

from __future__ import annotations

import csv
from pathlib import Path


PROMPTS_FILE = Path(__file__).with_name("prompts.csv")


def load_prompts(path: Path = PROMPTS_FILE) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        prompts = list(csv.DictReader(stream))
    required = {"id", "size", "prompt"}
    if not prompts or not required.issubset(prompts[0]):
        raise ValueError(f"{path.name} debe contener columnas {sorted(required)}")
    if any(not row["prompt"].strip() for row in prompts):
        raise ValueError(f"{path.name} contiene prompts vacíos")
    return prompts


def build_stages(
    profile: str,
    *,
    stage_seconds: int = 60,
    control_ramp_seconds: int = 10,
    control_total_seconds: int = 70,
    smoke_seconds: int = 8,
) -> list[dict[str, int]]:
    """Construye etapas acumuladas para saturación, control o smoke."""

    if profile == "saturation":
        targets = (1, 2, 4, 6, 10, 20, 40, 60)
        return [
            {"duration": stage_seconds * index, "users": users, "spawn_rate": 2}
            for index, users in enumerate(targets, start=1)
        ]
    if profile == "control":
        if control_total_seconds <= control_ramp_seconds:
            raise ValueError("CONTROL_TOTAL_SECONDS debe superar CONTROL_RAMP_SECONDS")
        return [
            {"duration": control_ramp_seconds, "users": 40, "spawn_rate": 4},
            {"duration": control_total_seconds, "users": 40, "spawn_rate": 4},
        ]
    if profile == "smoke":
        return [{"duration": smoke_seconds, "users": 2, "spawn_rate": 2}]
    raise ValueError("LOAD_PROFILE debe ser saturation, control o smoke")


def stage_at(stages: list[dict[str, int]], elapsed_seconds: float) -> dict[str, int] | None:
    for stage in stages:
        if elapsed_seconds < stage["duration"]:
            return stage
    return None
