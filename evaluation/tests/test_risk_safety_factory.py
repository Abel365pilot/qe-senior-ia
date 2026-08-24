import pytest

from risk_safety_factory import (
    RISK_GATE_CONTRACT,
    RiskSafetyConfigError,
    load_risk_safety_settings,
)


def test_project_url_is_fail_closed_and_normalized():
    settings = load_risk_safety_settings(
        {
            "AZURE_AI_PROJECT_URL": (
                "https://qe-resource.services.ai.azure.com/api/projects/qe-project/"
            )
        }
    )

    assert settings.project_url.endswith("/api/projects/qe-project")
    assert settings.indirect_attack_threshold == 0


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://qe-resource.services.ai.azure.com/api/projects/qe-project",
        "https://example.com/api/projects/qe-project",
        "https://qe-resource.services.ai.azure.com/not-a-project",
    ],
)
def test_project_url_rejects_unsafe_or_incomplete_values(url):
    with pytest.raises(RiskSafetyConfigError):
        load_risk_safety_settings({"AZURE_AI_PROJECT_URL": url})


def test_risk_contract_maps_indirect_attack_and_boolean_blockers():
    assert RISK_GATE_CONTRACT["D02"]["evaluator"] == "indirect_attack"
    assert "== true" in RISK_GATE_CONTRACT["D02"]["blocking_signal"]
    assert "== true" in RISK_GATE_CONTRACT["protected_material_dedicated"]["blocking_signal"]
