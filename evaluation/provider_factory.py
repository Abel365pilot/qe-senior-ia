"""Configuración fail-closed de jueces OpenAI-compatible o Azure OpenAI."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Mapping


class ProviderConfigError(ValueError):
    """La configuración del proveedor está ausente o es inválida."""


@dataclass(frozen=True)
class ProviderSettings:
    provider: str
    api_key: str
    model: str | None = None
    base_url: str | None = None
    azure_endpoint: str | None = None
    azure_deployment: str | None = None
    api_version: str | None = None
    extra_headers: dict[str, str] | None = None

    def safe_summary(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "azure_endpoint": self.azure_endpoint,
            "azure_deployment": self.azure_deployment,
            "api_version": self.api_version,
            "extra_header_names": sorted((self.extra_headers or {}).keys()),
            "credential_configured": bool(self.api_key),
        }


def _first(env: Mapping[str, str], *names: str) -> str:
    for name in names:
        value = str(env.get(name, "")).strip()
        if value:
            return value
    raise ProviderConfigError(f"Falta una variable requerida: {' o '.join(names)}.")


def load_provider_settings(env: Mapping[str, str] | None = None) -> ProviderSettings:
    values = os.environ if env is None else env
    provider = str(values.get("EVAL_PROVIDER") or values.get("MODEL_PROVIDER") or "openai_compatible").strip().casefold()
    if provider == "openai_compatible":
        raw_headers = str(values.get("EVAL_EXTRA_HEADERS_JSON", "")).strip()
        try:
            headers = json.loads(raw_headers) if raw_headers else None
        except json.JSONDecodeError as exc:
            raise ProviderConfigError("EVAL_EXTRA_HEADERS_JSON no es JSON válido.") from exc
        if headers is not None and not isinstance(headers, dict):
            raise ProviderConfigError("EVAL_EXTRA_HEADERS_JSON debe ser un objeto JSON.")
        return ProviderSettings(
            provider=provider,
            api_key=_first(values, "EVAL_API_KEY", "MODEL_API_KEY"),
            model=_first(values, "EVAL_MODEL", "MODEL_NAME"),
            base_url=_first(values, "EVAL_BASE_URL", "MODEL_BASE_URL").rstrip("/"),
            extra_headers={str(key): str(value) for key, value in (headers or {}).items()} or None,
        )
    if provider == "azure_openai":
        return ProviderSettings(
            provider=provider,
            api_key=_first(values, "AZURE_OPENAI_KEY"),
            azure_endpoint=_first(values, "AZURE_OPENAI_ENDPOINT").rstrip("/"),
            azure_deployment=_first(values, "AZURE_OPENAI_DEPLOYMENT"),
            api_version=str(values.get("AZURE_OPENAI_API_VERSION", "2024-10-21")).strip(),
        )
    raise ProviderConfigError("EVAL_PROVIDER debe ser openai_compatible o azure_openai.")


def build_model_config(settings: ProviderSettings) -> dict[str, object]:
    try:
        from azure.ai.evaluation import AzureOpenAIModelConfiguration, OpenAIModelConfiguration
    except ImportError as exc:
        raise ProviderConfigError("Instala requirements.txt antes de ejecutar la evaluación.") from exc

    if settings.provider == "openai_compatible":
        kwargs: dict[str, object] = {
            "type": "openai",
            "api_key": settings.api_key,
            "model": settings.model,
            "base_url": settings.base_url,
        }
        if settings.extra_headers:
            kwargs["extra_headers"] = settings.extra_headers
        return OpenAIModelConfiguration(**kwargs)
    return AzureOpenAIModelConfiguration(
        type="azure_openai",
        api_key=settings.api_key,
        azure_endpoint=settings.azure_endpoint,
        azure_deployment=settings.azure_deployment,
        api_version=settings.api_version,
    )
