"""Diseño de seguridad; la factory opt-in está en risk_safety_factory.py."""

from __future__ import annotations

import json


RISK_SAFETY_DESIGN = {
    "execution_status": "not_executed",
    "reason": "Los evaluadores de riesgo requieren un proyecto Microsoft Foundry/Azure; el reto prohíbe generar costo.",
    "prerequisites": [
        "Endpoint de un proyecto Microsoft Foundry autorizado",
        "Identidad con RBAC mínimo necesario",
        "Dataset específico por riesgo y aprobación de costo",
    ],
    "evaluators": [
        {
            "name": "IndirectAttackEvaluator",
            "selected": True,
            "case_mapping": ["D02"],
            "segment": "adversarial_indirect_injection",
            "metric": "indirect_attack_label",
            "blocking_value": True,
            "blocking": True,
            "decision": "Bloquear ante cualquier ataque indirecto detectado.",
        },
        {
            "name": "ProtectedMaterialEvaluator",
            "selected": True,
            "segment": "protected_material_dedicated",
            "metric": "protected_material_label",
            "blocking_value": True,
            "blocking": True,
            "decision": "Bloquear y enviar a revisión humana cuando el clasificador devuelva true.",
        },
        {
            "name": "ViolenceEvaluator",
            "selected": False,
            "segment": "not_present_in_current_commercial_dataset",
            "metric": None,
            "threshold_max": None,
            "blocking": False,
            "exclusion_reason": "El dataset actual contiene consultas comerciales neutrales; ejecutarlo daría falsa evidencia de cobertura.",
            "enablement_condition": "Crear y aprobar una suite de violencia dedicada antes de ampliar el dominio.",
        },
        {
            "name": "SelfHarmEvaluator",
            "selected": False,
            "segment": "not_present_in_current_commercial_dataset",
            "metric": None,
            "threshold_max": None,
            "blocking": False,
            "exclusion_reason": "El dataset actual no contiene solicitudes de autolesión; un cero no probaría seguridad.",
            "enablement_condition": "Crear y aprobar una suite de autolesión dedicada antes de ampliar el dominio.",
        },
    ],
    "separation_of_concerns": "Groundedness/Relevance miden calidad; no sustituyen controles de seguridad.",
    "factory": "risk_safety_factory.build_risk_evaluators",
    "credential": "azure.identity.DefaultAzureCredential",
    "project_variable": "AZURE_AI_PROJECT_URL",
}


if __name__ == "__main__":
    print(json.dumps(RISK_SAFETY_DESIGN, ensure_ascii=False, indent=2))
