"""Carga parametrizada para el emulador del Anexo B.

LOAD_PROFILE selecciona ``saturation``, ``control`` o ``smoke``. El perfil de
saturación es el predeterminado y su escala temporal puede acortarse solo para
validar el cableado mediante STAGE_SECONDS; la ejecución de evidencia usa 60 s.
"""

from __future__ import annotations

import csv
import itertools
import os
from pathlib import Path
from typing import Any

from locust import HttpUser, LoadTestShape, between, task


PROMPTS_FILE = Path(__file__).with_name("prompts.csv")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "128"))
TARGET_HOST = os.getenv("TARGET_HOST", "http://127.0.0.1:8000")
WAIT_MIN_SECONDS = float(os.getenv("WAIT_MIN_SECONDS", "0.05"))
WAIT_MAX_SECONDS = float(os.getenv("WAIT_MAX_SECONDS", "0.15"))


def load_prompts(path: Path = PROMPTS_FILE) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        prompts = list(csv.DictReader(stream))
    required = {"id", "size", "prompt"}
    if not prompts or not required.issubset(prompts[0]):
        raise ValueError(f"{path.name} debe contener columnas {sorted(required)}")
    if any(not row["prompt"].strip() for row in prompts):
        raise ValueError(f"{path.name} contiene prompts vacíos")
    return prompts


PROMPTS = load_prompts()
_prompt_cycle = itertools.cycle(PROMPTS)


def build_stages(
    profile: str,
    *,
    stage_seconds: int = 60,
    control_ramp_seconds: int = 10,
    control_total_seconds: int = 70,
    smoke_seconds: int = 8,
) -> list[dict[str, int]]:
    """Construye etapas acumuladas; es una función pura para poder probarla."""
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


class ChatCompletionUser(HttpUser):
    host = TARGET_HOST
    wait_time = between(WAIT_MIN_SECONDS, WAIT_MAX_SECONDS)

    @task
    def chat_completion(self) -> None:
        prompt = next(_prompt_cycle)
        payload = {
            "model": "llm-stub",
            "messages": [{"role": "user", "content": prompt["prompt"]}],
            "max_tokens": MAX_TOKENS,
        }

        with self.client.post(
            "/chat/completions",
            json=payload,
            name="/chat/completions",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                self._validate_success(response, payload)
                return
            if response.status_code == 429:
                self._validate_rate_limit(response)
                return
            response.failure(f"status inesperado {response.status_code}: {response.text[:160]}")

    @staticmethod
    def _validate_success(response: Any, payload: dict[str, Any]) -> None:
        try:
            body = response.json()
            choice = body["choices"][0]
            usage = body["usage"]
            content = choice["message"]["content"]
            expected_input = sum(
                len(message.get("content", "")) for message in payload["messages"]
            ) // 4
            valid = (
                body["object"] == "chat.completion"
                and choice["finish_reason"] == "stop"
                and len(content) == MAX_TOKENS
                and usage["prompt_tokens"] == expected_input
                and usage["completion_tokens"] == MAX_TOKENS
                and usage["total_tokens"] == expected_input + MAX_TOKENS
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            response.failure(f"JSON 200 inválido: {exc}")
            return
        if not valid:
            response.failure("contrato o conteo de tokens inválido en respuesta 200")
        else:
            response.success()

    @staticmethod
    def _validate_rate_limit(response: Any) -> None:
        try:
            body = response.json()
            retry_after = int(response.headers["Retry-After"])
        except (KeyError, TypeError, ValueError) as exc:
            response.failure(f"429 sin contrato válido: {exc}")
            return
        if body.get("error") != "rate_limit_exceeded" or retry_after < 1:
            response.failure("429 con cuerpo o Retry-After inválido")
        else:
            # Un 429 correcto sigue siendo un fallo de capacidad para que el error
            # porcentual y el autoStop de Azure reflejen la saturación real.
            response.failure(f"rate_limit_exceeded; Retry-After={retry_after}s")


class SaturationAndControlShape(LoadTestShape):
    def __init__(self) -> None:
        super().__init__()
        profile = os.getenv("LOAD_PROFILE", "saturation").lower()
        self.stages = build_stages(
            profile,
            stage_seconds=int(os.getenv("STAGE_SECONDS", "60")),
            control_ramp_seconds=int(os.getenv("CONTROL_RAMP_SECONDS", "10")),
            control_total_seconds=int(os.getenv("CONTROL_TOTAL_SECONDS", "70")),
            smoke_seconds=int(os.getenv("SMOKE_SECONDS", "8")),
        )

    def tick(self) -> tuple[int, float] | None:
        stage = stage_at(self.stages, self.get_run_time())
        if stage is None:
            return None
        return stage["users"], float(stage["spawn_rate"])
