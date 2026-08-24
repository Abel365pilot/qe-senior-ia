# Reto técnico — QE Senior con IA

Solución reproducible y sin costo para validar un asistente de compras en tres
capas complementarias: contrato funcional de Toolshop, capacidad de un endpoint
de IA emulado y calidad/seguridad de respuestas. La evidencia distingue siempre
entre lo ejecutado, lo diseñado y lo no ejecutado.

## Entregables

| Bloque | Implementación | Evidencia principal |
|---|---|---|
| A. Funcional | Karate DSL + Java 21; exactamente 4 escenarios, contratos JSON y helpers con `call` | `functional-api/evidence/functional-public-smoke-summary.txt` (4/4 público, diagnóstico) |
| B. Rendimiento | Stub local + Locust; rampa, control, prompts parametrizados y YAML Azure | `performance/results/` |
| C. Evaluación IA | 6 casos JSONL, Groundedness, Relevance, evaluadores propios y gate por segmento | `evaluation/results/` |
| Gobierno | Reglas de agente, bitácora de IA, Anexo A, CI sin consumo de modelo | `AGENTS.md`, `IA.md`, `.github/workflows/ci.yml` |
| Informe | Síntesis ejecutiva de dos páginas | `docs/informe-ejecutivo.pdf` |

## Resultado verificado

| Control | Resultado reproducido | Alcance |
|---|---:|---|
| Karate | 4/4 escenarios + 2/2 pruebas unitarias | Diagnóstico puntual contra Toolshop público; sin carga |
| Locust / Python | 9/9 pruebas; 2 smokes; rampa y control completos | Solo stub en `127.0.0.1` |
| Rampa 1→60 VU | 1 372 solicitudes; 8,53 % error; p95 19 s | Rodilla observada entre 4 y 6 VU; primer 429 a 40 VU |
| Control 40 VU | 467 solicitudes; 44,97 % error; p95 13 s | Throughput exitoso máximo observado: 3,3 req/s |
| Evaluación IA | 19 pruebas aprobadas, 1 opt-in omitida; 2 runs de 6/6 | Jueces Gemini 2.5 Flash Lite y Gemini 3.1 Flash Lite |
| Quality gate | **APROBADO**, cero fallos | Peor resultado por caso entre ambos jueces |

La evaluación entre dos modelos prueba robustez entre jueces, no repetibilidad
pura con un único juez. Una repetición adicional con Gemini 2.5 Flash Lite fue
bloqueada por la cuota gratuita observada de 20 solicitudes; no se alteraron los
resultados ni los umbrales para obtener la aprobación.

## Arquitectura y criterio de aislamiento

```text
Toolshop local <-- Karate (contrato/negocio)      [sin carga]
Stub localhost <-- Locust (capacidad/percentiles) [sin terceros]
Dataset JSONL  <-- Azure AI Evaluation + gate     [sin CI/modelo]
```

- Cada carrito usa un identificador nuevo y el login negativo usa un dominio
  reservado; ningún escenario depende del orden.
- La carga solo acepta `localhost`; los 429 válidos cuentan como fallo de
  capacidad para no maquillar la saturación.
- El gate falla cerrado ante datos ausentes, incompletos o no finitos. En dos
  corridas toma el peor puntaje de cada caso.
- CI ejecuta unidades, controles deterministas y un smoke local. No llama al
  proveedor del modelo, no hace una rampa de saturación ni carga Toolshop.

## Ejecución rápida

### 1. Funcional

La evidencia versionada ejecutó 4/4 escenarios contra la instancia pública, sin
carga, y 2/2 unidades. Docker Desktop quedó instalado, pero su daemon no pudo
iniciar porque Windows no tiene WSL habilitado; esa desviación está declarada y
no se presenta como prueba local. Para repetir en local se requiere Java 21,
Docker operativo y Toolshop iniciado. Las credenciales se inyectan en variables
de entorno; nunca se almacenan.

```powershell
cd functional-api
$env:TOOLSHOP_USER_EMAIL = Read-Host 'Email Toolshop'
$env:TOOLSHOP_USER_PASSWORD = Read-Host 'Password Toolshop' -MaskInput
.\mvnw.cmd clean test -Dkarate.env=local
```

El detalle del arranque local, configuración y mitigación de intermitencia está
en [`functional-api/README.md`](functional-api/README.md).

### 2. Rendimiento

```powershell
cd performance
python -m pip install -r requirements-dev.txt
python -m pytest -q
.\run-local.ps1 -Profile saturation -SkipInstall
.\run-local.ps1 -Profile control -SkipInstall
```

`performance/config.yaml` es un diseño equivalente para Azure Load Testing; no
se ejecuta en Azure porque `127.0.0.1` allí sería el motor administrado y crear
recursos contradice el requisito de costo cero.

### 3. Evaluación IA

```powershell
cd evaluation
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe quality_gate.py --results results\run1_gemini-2.5-flash-lite.json results\run2_gemini-3.1-flash-lite.json
```

Las variables del proveedor y los códigos de salida (`0` aprobado, `1` calidad
insuficiente, `2` entrada/configuración inválida) se documentan en
[`evaluation/README.md`](evaluation/README.md). `PF_WORKER_COUNT=1` se fuerza en
el runner para controlar consumo. Las nuevas llamadas al juez son opt-in y no
forman parte de CI.

## Decisiones senior

- **p95 sobre promedio.** El promedio mezcla respuestas 200 encoladas con 429
  rápidos y puede mejorar cuando el sistema rechaza más tráfico. p95 se lee junto
  con throughput exitoso y error.
- **Cuatro escenarios, no más.** Cubren los tres criterios de aceptación y un
  negativo real sin convertir la suite en una colección redundante.
- **Dataset pequeño pero estratificado.** Incluye 2 casos respondibles, 1 no
  respondible y 3 adversariales. Sirve como gate inicial, no como estimación
  estadística de producción.
- **Evidencia honesta.** Un resultado de diseño, fixture o smoke nunca se etiqueta
  como ejecución completa ni como métrica del modelo.

## Seguridad y reproducibilidad

- `.env`, claves y artefactos sensibles están ignorados por Git.
- No hay facturación, recursos Azure, carga a terceros ni secretos en el código.
- Versiones fijadas en `pom.xml` y archivos `requirements*.txt`.
- El informe, los CSV crudos, los resúmenes y el historial permiten reconstruir
  cada conclusión sin depender de capturas aisladas.

Autor: Carlos Abel Dominguez Bautista — 24 de agosto de 2026.
