from risk_safety_design import RISK_SAFETY_DESIGN


def test_selected_risk_evaluators_have_numeric_threshold_and_blocking_policy():
    selected = [item for item in RISK_SAFETY_DESIGN["evaluators"] if item["selected"]]
    assert {item["name"] for item in selected} == {
        "IndirectAttackEvaluator",
        "ProtectedMaterialEvaluator",
    }
    assert all(item["threshold_max"] == 0.0 and item["blocking"] is True for item in selected)


def test_excluded_evaluators_have_explicit_reason_and_enablement_condition():
    excluded = [item for item in RISK_SAFETY_DESIGN["evaluators"] if not item["selected"]]
    assert {item["name"] for item in excluded} == {"ViolenceEvaluator", "SelfHarmEvaluator"}
    assert all(item["exclusion_reason"] and item["enablement_condition"] for item in excluded)
