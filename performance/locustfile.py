"""Carga parametrizada para el emulador del Anexo B.

LOAD_PROFILE selecciona ``saturation``, ``control`` o ``smoke``. El perfil de
saturación es el predeterminado y su escala temporal puede acortarse solo para
validar el cableado mediante STAGE_SECONDS; la ejecución de evidencia usa 60 s.
"""

from __future__ import annotations

import itertools
import os
from typing import Any

from locust import HttpUser, LoadTestShape, between, task

from load_profile import build_stages, load_prompts, stage_at

MAX_TOKENS = int(os.getenv("MAX_TOKENS", "128"))
# Sin valor por defecto deliberadamente: local lo inyecta run-local.ps1 y Azure
# debe recibir la URL del stub aislado al crear la prueba. Así un artefacto
# olvidado no termina apuntando al loopback del motor gestionado.
TARGET_HOST = os.getenv("TARGET_HOST")
WAIT_MIN_SECONDS = float(os.getenv("WAIT_MIN_SECONDS", "0.05"))
WAIT_MAX_SECONDS = float(os.getenv("WAIT_MAX_SECONDS", "0.15"))


PROMPTS = load_prompts()
_prompt_cycle = itertools.cycle(PROMPTS)


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
