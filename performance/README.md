# Bloque B - Rendimiento del endpoint de IA

Este bloque prueba exclusivamente el emulador local del Anexo B. No dirige carga a Toolshop, al proveedor del modelo ni a terceros.

## Diseño ejecutable

- `llm_stub.py`: transcripción fiel del Anexo B; solo biblioteca estándar.
- `locustfile.py`: solicitudes parametrizadas, validación del contrato 200/429 y perfiles `saturation`, `control` y `smoke`.
- `prompts.csv`: 12 prompts únicos en tres tamaños.
- `run-local.ps1`: fija el experimento, arranca y detiene el stub, ejecuta Locust y guarda CSV, HTML, logs y resumen.
- `experiment_policy.json` + `validate_experiment.py`: gate fail-closed que separa salud del servicio de validez del experimento.
- `experiment_manifest.json`: parámetros y metadatos preservados; lo no capturado queda `null`, no inferido.
- `config.yaml`: artefacto de Azure Load Testing de diseño; no se ejecuta en Azure.
- `tests/`: contrato determinista del stub, perfil, prompts y configuración Azure.

## Parámetros fijados

| Parámetro | Valor | Motivo |
|---|---:|---|
| `TPM` | 34 000 | Queda ligeramente por encima del techo de concurrencia en régimen estable y permite observar después los 429 al crecer la cola. |
| `MAX_CONC` | 4 | Hace visible la espera desde 6 usuarios sin exigir una máquina grande. |
| `BASE_MS` | 250 ms | Mantiene la latencia base del Anexo B. |
| `MS_PER_TOK` | 8 ms | Mantiene la pendiente del Anexo B. |
| `max_tokens` | 128 | Respuesta constante y comparable entre etapas. |

Con 128 tokens de salida, el servicio medio ocupa `250 + 128 x 8 = 1 274 ms`. El techo por concurrencia es `4 / 1.274 = 3.14 respuestas 200/s`. Los prompts se diseñaron alrededor de 40 tokens de entrada, por lo que el techo teórico de cuota es aproximadamente `34 000 / ((40 + 128) x 60) = 3.37 req/s`. Así, la concurrencia corta primero y eleva progresivamente la latencia; cuando la cola reserva suficientes tokens dentro de la ventana de 60 segundos, aparece el segundo régimen con 429.

## Perfiles

La rampa completa mantiene cada nivel durante 60 segundos: `1, 2, 4, 6, 10, 20, 40, 60` usuarios, con incorporación de 2 usuarios/s. Cruza deliberadamente `MAX_CONC=4` y dura 8 minutos.

El control sube a 40 usuarios a 4 usuarios/s y se mantiene hasta completar 70 segundos. Debe ejecutarse con un stub recién iniciado para reiniciar la ventana TPM. El smoke usa 2 usuarios durante 8 segundos y solo comprueba el cableado.

## Ejecución local

Desde PowerShell, en esta carpeta:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
./run-local.ps1 -Profile smoke -SkipInstall
./run-local.ps1 -Profile saturation -SkipInstall
./run-local.ps1 -Profile control -SkipInstall
```

Cada ejecución crea una carpeta fechada bajo `results/`. Un código Locust 1 es esperado en saturación/control si los 429 se registran correctamente como fallos de capacidad; el smoke debe terminar en 0.
Después de resumir los CSV, `run-local.ps1` ejecuta el gate del perfil y escribe
`experiment-gate.json`. Sus códigos son `0=aprobado`, `1=política incumplida` y
`2=evidencia inválida`.

El gate evita un falso verde frecuente: una rampa que nunca satura puede tener
0% de errores, pero no demuestra capacidad. Por eso el smoke exige p95 <=2,5 s
y cero errores, mientras que rampa/control exigen alcanzar la carga diseñada,
cruzar p95 y error, observar 429 desde 40 VU y mantener el throughput exitoso en
el rango 2,5-4,5 req/s previsto por el modelo analítico.

### Evidencia ejecutada en esta entrega

Se verificaron 17 pruebas deterministas y todas aprobaron. Dos smokes contra un
stub nuevo consolidaron 10 solicitudes cada uno, 0 fallos y p95 de 1 500/1 400
ms.

La rampa completa `saturation-20260824-171114` ejecutó los ocho niveles durante
8 minutos: 1 372 solicitudes, 117 fallos (8.53%), p95 de 19 000 ms y máximo de
60 usuarios. Frente al baseline estable de 1 500 ms (mediana de las últimas 30
muestras de la etapa de 4 VU), el p95 cruzó 2x a 10 VU; a 6 VU fue 2 200 ms
(1,47x). Superó el SLO de
5 000 ms a 20 VU. El primer 429 apareció a los 419 s con 40 usuarios;
el error acumulado cruzó 5% al final con 60. El throughput exitoso se estabilizó
en 3.3–3.4 req/s aunque el intentado alcanzó 12.5 req/s.

El control independiente `control-20260824-172019` arrancó un stub nuevo y subió
a 40 usuarios: 467 solicitudes, 210 fallos (44.97%) y p95 de 13 000 ms. Cruzó
5 000 ms a los 10 s y registró el primer 429 a los 55 s. Repitió el techo de 3.3
req/s exitosas y confirma que el resultado no depende de la historia de la rampa.
El cierre drenó peticiones durante 30 s; los cambios de `User Count` del drenaje
no se interpretan como nuevos niveles.

Los HTML, CSV de estadísticas/historia/fallos, logs del stub y resúmenes
JSON/Markdown están versionados. Los 429 se registran deliberadamente como fallo
de capacidad, por lo que el código Locust 1 de rampa y control es el resultado
esperado, no un fallo del harness.

Para cifras agregadas, `locust_stats.csv` es el snapshot canónico consumido por
`analyze_results.py`, y `summary.json` es su resumen trazable. El HTML de Locust
se conserva para exploración visual; al cerrar puede capturar una muestra entre
el último flush del CSV y el reporte. En el control versionado el HTML muestra
468 solicitudes y el CSV/JSON canónico 467; las conclusiones usan 467 sin
alterar ningún resultado.

## Lectura de métricas

Se usa p95 como SLO de latencia porque refleja la cola que experimenta la mayoría de los usuarios sin depender de un extremo aislado. El promedio es engañoso: mezcla respuestas 200 lentas por espera con 429 rápidos, y puede incluso bajar cuando el servicio está rechazando más tráfico. Por eso se interpretan juntos p95/p99, throughput exitoso y porcentaje de error.

El stub no emula streaming, caché, batching, longitud de salida variable, timeouts de red, fallos del proveedor, distribución real de tokens, límites por cuenta/modelo, moderación, autoscaling ni variabilidad por hardware. Sus tokens de entrada son una aproximación de cuatro caracteres por token y reserva la cuota antes de entrar al semáforo.

## Azure Load Testing: equivalencia y límite

`config.yaml` sigue el esquema `v0.1`, declara Locust, `prompts.csv`, `locust.conf`, p95, porcentaje de error y parada automática. Una instancia de motor no equivale a un usuario virtual: los usuarios los gobierna `LoadTestShape`, mientras que `engineInstances` aporta generadores de carga y cambia la capacidad del inyector. Antes de comparar Azure con local se debe conservar un solo motor y verificar que no sea el cuello de botella.

El emulador vive en `127.0.0.1` del equipo local. En Azure, esa dirección sería
el propio motor gestionado, no este equipo. Por ello el YAML no incluye
`TARGET_HOST`: una ejecución real debe exponer una instancia aislada del stub e
inyectar su URL como variable de entorno al crear la prueba. `locustfile.py`
tampoco tiene un host por defecto; si se omite la URL, Locust falla antes de
enviar tráfico. Esta entrega no despliega ese stub ni crea recursos, por lo que
el artefacto Azure queda diseñado y validado, pero no ejecutado.

Los umbrales del YAML se documentan como parte del artefacto y deben contrastarse con los resultados versionados: p95 mayor que 5 000 ms o error mayor que 5% falla la prueba; `autoStop` interrumpe si el error supera 20% durante 30 segundos. El smoke de CI, si se incorpora, debe usar umbrales más laxos porque un runner comparte CPU entre stub e inyector y no es comparable con la corrida local.
