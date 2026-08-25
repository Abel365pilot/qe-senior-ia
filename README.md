# Reto técnico — QA Automation Senior con IA

[![CI determinista](https://github.com/Abel365pilot/qe-senior-ia/actions/workflows/ci.yml/badge.svg)](https://github.com/Abel365pilot/qe-senior-ia/actions/workflows/ci.yml)
[![Toolshop aislado](https://github.com/Abel365pilot/qe-senior-ia/actions/workflows/toolshop-local.yml/badge.svg)](https://github.com/Abel365pilot/qe-senior-ia/actions/workflows/toolshop-local.yml)

Solución reproducible y fail-closed para validar un asistente de compras en tres
capas: contrato funcional, capacidad del endpoint IA emulado y calidad/seguridad
de respuestas. Cada conclusión enlaza riesgo, prueba, evidencia y gate; lo
ejecutado se separa de lo diseñado y de lo pendiente.

## Entregables

| Bloque | Implementación | Evidencia/gate |
|---|---|---|
| A. API funcional | Karate + Java 21; exactamente 4 escenarios, 7 helpers, 6 contratos, `BigDecimal`, cleanup | 18 pruebas auxiliares; reportes Karate/JUnit; [Toolshop Docker #1 verde](https://github.com/Abel365pilot/qe-senior-ia/actions/runs/32790477664) |
| B. Rendimiento | Stub local + Locust; 12 prompts; rampa, control y smoke; Azure YAML | CSV/HTML/JSON + `experiment-gate.json` por perfil |
| C. Evaluación IA | 6 JSONL (2/1/3), Azure AI Evaluation, 3 controles propios | same-judge PASS, cross-judge PASS, negative-control EXPECTED_FAIL |
| Gobierno | Reglas, bitácora, matriz, estrategia, CI sin modelo | `release_gate.py`, evidencias SDK sanitizadas |
| Informe | Síntesis ejecutiva | PDF A4 de máximo 2 páginas |

La trazabilidad completa de los 13 criterios está en
[`docs/traceability-matrix.md`](docs/traceability-matrix.md) y la estrategia de
calidad en [`docs/senior-qa-strategy.md`](docs/senior-qa-strategy.md).

## Resultado verificable

| Control | Resultado | Alcance honesto |
|---|---:|---|
| Funcional sin red | 18/18 pruebas Java | Configuración, contratos, arquitectura, datos y oracle; no prueba Toolshop |
| Karate Toolshop aislado | [PASS; 4/4 escenarios](https://github.com/Abel365pilot/qe-senior-ia/actions/runs/32790477664) | Docker local, SUT/OpenAPI fijados, health, seed, cleanup y artefacto de 377 KB |
| CI principal | [PASS; 3/3 jobs](https://github.com/Abel365pilot/qe-senior-ia/actions/runs/32790477741) | Funcional sin red, calidad determinista y smoke de rendimiento |
| Karate diagnóstico | 4/4 escenarios | Instancia pública, versión previa; no sustituye el SUT aislado |
| Locust/Python | 17/17 pruebas; 2 smokes; rampa y control | Solo stub en localhost |
| Rampa 1→60 VU | 1 372 solicitudes; 8,528 % error; p95 19 s | Cola visible a 6 VU; 2× baseline estable a 10; SLO excedido a 20 |
| Control 40 VU | 467 solicitudes; 44,968 % error; p95 13 s | Techo exitoso repetido: 3,3 req/s |
| Evaluación buena | 3 runs completos de 6/6 | Dos con el mismo juez y uno con juez alterno |
| Repetibilidad | PASS; acuerdo exacto 100 %; delta 0 | Gemini 3.1 Flash Lite, mismas seis respuestas |
| Robustez entre jueces | PASS; delta máximo 2 | No equivale a repetibilidad |
| Control negativo real | EXPECTED_FAIL; código 1; 10 fallos | Seis respuestas malas evaluadas por el SDK, no fixture |
| Confianza | 6/6; Wilson 95 % inferior 0,6097 | Descriptivo; dataset fijo, sin inferencia productiva |

## Proveedor y cuota observada

La evaluación usó Google AI Studio mediante su endpoint compatible con OpenAI,
con `gemini-2.5-flash-lite` y `gemini-3.1-flash-lite`. En un intento previo de
repetición, Gemini 2.5 Flash Lite agotó la cuota gratuita disponible; el evento
describe aquella ejecución y no se presenta como un límite universal, porque
Google no expuso una cuota única y estable para el proyecto. Las corridas
definitivas con Gemini 3.1 Flash Lite completaron con
`PF_WORKER_COUNT=1`. Antes de repetir el dataset completo se debe verificar la
cuota vigente del proyecto; el runner no hace reintentos ciegos ni llama al
modelo desde CI.

## Arquitectura y aislamiento

```text
Toolshop Docker fijado <-- Karate      contrato y negocio; nunca carga
Stub localhost         <-- Locust      capacidad y percentiles; cero terceros
JSONL fijo              <-- SDK + gate calidad, estabilidad y control negativo
```

- Toolshop queda fijado al commit
  `9e7736c3841ec2bbb9a6822c9e6602353b7b9a65`; su OpenAPI tiene SHA-256
  `a1b79c7e0df4ee64f3ae0fbc76401c1e2071fc5fbaa00bb8b89d482df09e9580`.
- El workflow `toolshop-local.yml` levanta ese SUT en Docker, espera salud,
  ejecuta 4 escenarios y conserva OpenAPI, estado, logs y reportes. Nunca llama
  a la instancia pública.
- Cada carrito usa un ID nuevo; `X-QE-Run-Id` correlaciona fallos y
  `afterScenario` intenta una limpieza defensiva sin retry ciego.
- Locust registra 429 como fallos de capacidad. El `service_gate` de smoke exige
  0 % error y p95 ≤2,5 s; el `experiment_gate` exige demostrar saturación.
- El gate IA falla ante datos ausentes/no finitos, mezcla de variantes o
  evidencia duplicada. CI reproduce decisiones sin invocar ningún modelo.

## Reproducción

### A. Toolshop local

```powershell
git clone https://github.com/testsmith-io/practice-software-testing.git
cd practice-software-testing
git checkout --detach 9e7736c3841ec2bbb9a6822c9e6602353b7b9a65
docker compose -f docker-compose.prod.yml up --pull missing -d

cd ..\qe-senior-ia\functional-api
$env:TOOLSHOP_USER_EMAIL = Read-Host 'Email Toolshop'
$env:TOOLSHOP_USER_PASSWORD = Read-Host 'Password Toolshop' -MaskInput
.\mvnw.cmd clean test -Dkarate.env=local
```

Las credenciales solo se inyectan por entorno. Configuración, seguridad y causa
precisa de intermitencia: [`functional-api/README.md`](functional-api/README.md).

### B. Rendimiento local

```powershell
cd performance
python -m pip install -r requirements-dev.txt
python -m pytest -q
.\run-local.ps1 -Profile smoke -SkipInstall
.\run-local.ps1 -Profile saturation -SkipInstall
.\run-local.ps1 -Profile control -SkipInstall
```

`performance/config.yaml` sigue el esquema Azure Load Testing v0.1, pero no
incluye loopback: `TARGET_HOST` debe inyectarse con la URL de un stub aislado
accesible. No se creó ni ejecutó ningún recurso Azure.

### C. Evaluación y gates sin red

```powershell
cd evaluation
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe quality_gate.py --results results\run2_gemini-3.1-flash-lite.json results\evaluation_full_good_20260824T230559Z.json --report results\quality_gate_good.json
```

El gate usa `0=PASS`, `1=calidad insuficiente` y `2=evidencia/configuración
inválida`. El control negativo debe retornar 1. Detalle:
[`evaluation/README.md`](evaluation/README.md).

## Decisión de liberación

- **GO para demostración técnica:** código, datos, evidencia y gates son
  auditables; el CI principal y Toolshop Docker están verdes sobre `356e86c`.
- **NO-GO para producción:** todavía exige etiquetado humano, 35 casos como
  mínimo (50 recomendados) por segmento para calibración y resolver capacidad
  antes de aceptar 20 VU. Repetir las mismas seis respuestas no aumenta `n`.

## Seguridad y reproducibilidad

- `.env`, claves, raw SDK interno, `.venv` y `target/` están ignorados.
- La evidencia SDK pública conserva razones, tokens, scores, modelo y SHA-256;
  elimina prompts internos, headers, Studio URL y credenciales.
- Versiones están fijadas; CI usa permisos mínimos, timeouts, concurrencia
  cancelable y publica artefactos aun ante fallo.
- `scripts/release_gate.py` verifica entregables, dataset, escenarios,
  repetibilidad, control negativo, carga, referencias y secretos.

Autor: Carlos Abel Dominguez Bautista — 24 de agosto de 2026.
