import pytest

from provider_factory import ProviderConfigError, build_model_config, load_provider_settings


def test_openai_compatible_configuration_is_explicit_and_safe_to_summarize():
    settings = load_provider_settings(
        {
            "EVAL_PROVIDER": "openai_compatible",
            "EVAL_API_KEY": "secret-used-only-in-memory",
            "EVAL_MODEL": "judge-model",
            "EVAL_BASE_URL": "https://provider.example/v1/",
        }
    )
    assert settings.base_url == "https://provider.example/v1"
    assert "api_key" not in settings.safe_summary()
    assert settings.safe_summary()["credential_configured"] is True


def test_azure_configuration_is_config_only():
    settings = load_provider_settings(
        {
            "EVAL_PROVIDER": "azure_openai",
            "AZURE_OPENAI_KEY": "secret-used-only-in-memory",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/",
            "AZURE_OPENAI_DEPLOYMENT": "judge",
        }
    )
    assert settings.azure_deployment == "judge"
    assert settings.azure_endpoint == "https://example.openai.azure.com"


def test_root_model_aliases_are_supported_without_exposing_secret():
    settings = load_provider_settings(
        {
            "MODEL_PROVIDER": "openai_compatible",
            "MODEL_API_KEY": "secret-used-only-in-memory",
            "MODEL_NAME": "gemini-2.5-flash-lite",
            "MODEL_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai/",
        }
    )
    assert settings.model == "gemini-2.5-flash-lite"
    assert settings.base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert "api_key" not in settings.safe_summary()


def test_missing_credential_fails_closed():
    with pytest.raises(ProviderConfigError):
        load_provider_settings(
            {
                "EVAL_PROVIDER": "openai_compatible",
                "EVAL_MODEL": "judge-model",
                "EVAL_BASE_URL": "https://provider.example/v1",
            }
        )


def test_sdk_model_configuration_has_explicit_connection_type():
    pytest.importorskip("azure.ai.evaluation")
    settings = load_provider_settings(
        {
            "MODEL_PROVIDER": "openai_compatible",
            "MODEL_API_KEY": "test-only",
            "MODEL_NAME": "judge",
            "MODEL_BASE_URL": "https://provider.invalid/v1",
        }
    )
    assert build_model_config(settings)["type"] == "openai"
