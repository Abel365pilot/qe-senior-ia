# Matriz de trazabilidad - QA Automation Senior

Estados: **Cumplido** = artefacto y evidencia disponibles; **Parcial** = control
implementado con una evidencia pendiente; **Pendiente** = no implementado. El
riesgo residual nunca se convierte en aprobado por redacción.

Evidencia publicada sobre `356e86c`: [CI principal #2][ci-run] y
[Toolshop Docker + Karate #1][toolshop-run], ambos en estado `Success`.

## Entregables obligatorios

| ID | Entregable | Evidencia | Estado y riesgo residual |
|---|---|---|---|
| E1 | Repositorio completo | `functional-api/`, `performance/`, `evaluation/` | **Cumplido** |
| E2 | README reproducible, variables, proveedor y cuota | README raíz y por bloque; `.env.example`; SUT fijado por commit/OpenAPI SHA; [run Docker verde][toolshop-run] | **Cumplido**; ejecución reproducible y artefacto publicados |
| E3 | Informe máximo 2 páginas | `docs/informe-ejecutivo.pdf` | **Cumplido**: 2 páginas A4 renderizadas y revisadas |
| E4 | Evidencia de carga y evaluación | CSV/HTML/JSON; tres runs buenos; control negativo; evidencia SDK sanitizada | **Cumplido**; dataset de 6 casos no representa producción |
| E5 | Artefactos Azure sin ejecutar | `performance/config.yaml`; `risk_safety_factory.py` | **Cumplido como diseño**; no ejecutado para evitar costo |
| E6 | Bitácora, auditoría y reglas del agente | `IA.md`, `AGENTS.md` | **Cumplido** |

## Criterios de evaluación

| Criterio | Pregunta de calidad | Control/evidencia | Gate | Estado y riesgo residual |
|---|---|---|---|---|
| N1 Funcionalidad | ¿CA 1-3 y el negativo funcionan en un SUT aislado? | 4 escenarios; contratos; 18 auxiliares; [4/4 contra Toolshop Docker fijado][toolshop-run] | HTTP, contrato, semántica y cleanup | **Cumplido**; la evidencia hermética y la del SUT se mantienen separadas |
| N2 Diseño/legibilidad | ¿La abstracción conserva intención? | 7 helpers con `call`; configuración fail-fast; oracle `BigDecimal`; tests de arquitectura | Build + unidades + presupuesto exacto de 4 escenarios | **Cumplido** |
| N3 Datos | ¿Dos corridas interfieren? | UUID/run ID, email `example.invalid`, carrito nuevo, `afterScenario`, sin retry global | Sin orden implícito; cleanup observable | **Cumplido** en suite; un transporte caído aún puede impedir cleanup |
| N4 Carga | ¿La rampa cruza techos y usa prompts variados? | 12 prompts; 1→60 VU; control independiente; manifiesto; política | Gate exige carga, p95, error, 429 y throughput exitoso | **Cumplido** sobre stub local |
| N5 Dataset | ¿Cubre respuestas buenas, no fundamentadas y ataques? | 6 JSONL 2/1/3; corrida buena y control negativo real | Contrato exacto + variante separada | **Cumplido** para muestra fija; cobertura estadística insuficiente |
| N6 Evaluadores/gate | ¿Detecta fallos y es estable? | Groundedness, Relevance y 3 controles; 3 runs buenos + 1 malo | 0/1/2 fail-closed; peor score por caso | **Cumplido** para dataset fijo; Wilson 95 % inferior 0,6097 impide inferencia productiva |
| O7 Intermitencia | ¿Diagnostica sin retry ciego? | Carrera catálogo→carrito, `X-QE-Run-Id`, body/status preservados, SUT fijado | Fallo conserva causa; una limpieza defensiva | **Cumplido**; [run Docker][toolshop-run] sin retry global y con logs publicados |
| O8 Azure Load Testing | ¿YAML y local son equivalentes y seguros? | Esquema v0.1, Locust, prompts, 1 motor; target inyectado en runtime | p95 >5 s, error >5 %, autoStop >20 %/30 s | **Cumplido como diseño**, no ejecutado; requiere stub aislado accesible |
| O9 Riesgo/seguridad | ¿La configuración refleja la semántica SDK? | Factory con `DefaultAzureCredential`; D02→Indirect Attack; booleano Protected Material | Cualquier label `true` bloquea | **Cumplido como diseño**, no ejecutado |
| N10 Análisis | ¿Las conclusiones nacen de los CSV? | Baseline = mediana últimas 30 muestras a 4 VU; control 40 VU | Cola visible 6 VU; 2× a 10; SLO a 20 | **Cumplido**; no extrapola el stub a producción |
| O11 Uso de IA | ¿Hay gobierno y revisión humana? | Prompt literal, defecto real, corrección, tarea no delegada, auditoría | Evidencia ejecutable domina la narrativa | **Cumplido** |
| P12 Documentación | ¿Un tercero puede reproducir/auditar? | Versiones, SUT/OpenAPI SHA, comandos, CI, manifiesto, SDK sanitizado | `scripts/release_gate.py` | **Cumplido**; [CI][ci-run] y [Toolshop][toolshop-run] publican evidencia consultable |
| P13 Honestidad | ¿Separa ejecutado/diseñado/no cubierto? | Etiquetas y decisión condicionada | GO demo / NO-GO producto | **Cumplido** |

## Criterios de aceptación

| CA | Cobertura | Evidencia | Estado |
|---|---|---|---|
| 1. Login válido e inválido | Karate escenarios 1 y 2 | [Toolshop Docker #1][toolshop-run] | **Cumplido** |
| 2. Buscar/filtrar catálogo | Karate escenario 3 | Contrato paginado, texto y categoría en [run aislado][toolshop-run] | **Cumplido** |
| 3. Cantidad/total carrito | Karate escenario 4 + unidades | Cantidad 2, descuentos, `BigDecimal`, cleanup en [run aislado][toolshop-run] | **Cumplido** |
| 4. Compra hasta confirmación | Fuera del track API elegido, que exige CA 1-3 | No se declara ejecutado | **No requerido por el track** |
| 5. Endpoint IA bajo carga | Locust contra Anexo B | Rampa/control y gates | **Cumplido**: cola 6 VU, 2× a 10, SLO a 20, primer 429 a 40 |
| 6. Calidad fundamentada/relevante | SDK + controles deterministas | Same-judge PASS; cross-judge PASS; negative EXPECTED_FAIL | **Cumplido para dataset fijo** |

## Decisión senior

- **GO — demostración técnica:** arquitectura, automatización, evidencia y gates
  son utilizables y auditables.
- **NO-GO — liberación productiva:** aunque el run Docker ya está verde, se
  requieren 35 casos como mínimo (50 recomendados) por segmento, etiquetas
  humanas, calibración del juez y resolver capacidad antes de aceptar 20 VU.
- Un smoke prueba cableado; una rampa prueba el perfil del stub; un fixture
  prueba el gate. Ninguno se etiqueta como comportamiento productivo.

[ci-run]: https://github.com/Abel365pilot/qe-senior-ia/actions/runs/32790477741
[toolshop-run]: https://github.com/Abel365pilot/qe-senior-ia/actions/runs/32790477664
