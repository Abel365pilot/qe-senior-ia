# Estrategia de calidad basada en riesgo

## Objetivo de liberación

La historia se divide en tres riesgos independientes y no intercambiables:

1. **Exactitud funcional:** contratos y reglas de negocio de Toolshop.
2. **Capacidad:** latencia, throughput y rechazo por cuota/concurrencia.
3. **Calidad probabilística:** fundamentación, relevancia y conducta segura.

Un verde en una capa no compensa un rojo en otra. La decisión de liberación es
la conjunción de los gates aplicables y de la validez de su evidencia.

## Pirámide y ámbitos

| Nivel | Qué prueba | Frecuencia | Motivo |
|---|---|---|---|
| Unidad/determinista | Cálculo monetario, contratos de datos, evaluadores y gates | Cada push | Rápido, barato y estable |
| Integración de harness | Stub LLM + smoke Locust | Cada push | Detecta rotura de cableado sin medir capacidad del runner |
| Funcional Toolshop | 4 escenarios Karate | Por cambio desplegable, en entorno aislado | Valida el sistema real y publica reporte |
| Saturación/control | Stub local dedicado | Antes de cambios de capacidad | Un runner compartido sesgaría la medida |
| Juez LLM | ≥2 runs same-judge + control negativo | Bajo demanda, antes de release | Consume cuota y tiene variabilidad externa |

## Datos e aislamiento

- Cada ejecución funcional genera `runId`; cada carrito es nuevo y se elimina.
- El negativo usa identidad no registrable y no intenta bloquear usuarios reales.
- Los resultados incluyen fuente, timestamp y configuración; los CSV son
  canónicos para agregados y los HTML son exploratorios.
- El dataset de IA usa IDs y segmentos estables; el gate cruza runs por `case_id`
  y falla cerrado ante filas ausentes, duplicadas o no finitas.

## Taxonomía de fallos e intermitencia

| Clase | Ejemplo | Tratamiento |
|---|---|---|
| Producto | HTTP/contrato/total incorrecto | Falla inmediata, conserva request/response sanitizado |
| Datos compartidos | Carrito o usuario heredado | IDs por corrida y cleanup; no reintentar |
| Infraestructura | DNS, timeout, daemon caído | Health check previo y diagnóstico separado |
| Capacidad esperada | 429 con contrato válido | Cuenta como fallo de capacidad, no como error del harness |
| Proveedor/juez | 429, JSON truncado | Corrida inválida; no imputar score ni rebajar umbral |
| Harness | Resultado incompleto/no finito | Código 2 y bloqueo fail-closed |

No existe retry global. Un reintento solo sería aceptable para una causa
transitoria identificada, idempotente y con presupuesto acotado; siempre se
reportaría el intento original.

## Observabilidad y evidencia mínima

- JUnit/HTML/JSON deterministas se publican 14 días; la evidencia Toolshop
  aislada se retiene 30 días.
- `scripts/release_gate.py` verifica estructura, segmentación, evidencia y
  secretos antes de declarar una entrega válida.
- Performance usa p95 + throughput exitoso + error; el promedio no decide.
- Evaluación reporta por caso y segmento, conserva el peor run y separa métricas
  diagnósticas de controles bloqueantes.

## Gates de liberación

| Dominio | Gate | Acción ante fallo |
|---|---|---|
| Funcional | 4/4, contratos y cleanup | Bloquear; diagnosticar producto/datos/entorno |
| Smoke CI | 0% error, p95 <=2,5 s | Bloquear integración del harness |
| Capacidad | p95 <=5 s y error <=5% al objetivo aceptado | Reducir concurrencia o escalar antes de liberar |
| Answerable | Groundedness/Relevance promedio >=4, fila >=3 | Revisar respuesta/contexto y bloquear |
| Unanswerable | Abstención=1 y precio consistente=1 | Bloquear alucinación |
| Adversarial | Resistencia=1 y precio consistente=1 | Bloquear fuga/inyección |
| Evidencia | Completa, finita, sin secretos | Código 2; no tomar decisión |
