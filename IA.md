# Bitácora y auditoría de IA

## Herramientas empleadas

| Herramienta | Uso en el reto | Control humano aplicado |
|---|---|---|
| OpenAI Codex | Lectura del reto, diseño de arquitectura, generación de código, pruebas y documentación | Requisitos del PDF convertidos en checks verificables; ningún resultado crudo se aceptó sin ejecución |
| Agentes paralelos de Codex | Implementación separada de Karate, Locust, evaluación y auditoría | Integración, pruebas cruzadas y corrección de defectos observados |
| Gemini 2.5 Flash Lite y Gemini 3.1 Flash Lite (Google AI Studio) | Modelos juez de Groundedness y Relevance mediante `azure-ai-evaluation==1.18.3` | Dataset sembrado, PF_WORKER_COUNT=1, controles deterministas y gate por segmento; se conserva el peor resultado por caso |

La IA se utilizó como acelerador de ingeniería. Las decisiones de alcance, los umbrales, la interpretación de resultados y la aceptación final se mantienen bajo responsabilidad humana.

Las dos corridas integrales son una validación cruzada entre jueces. No prueban
repetibilidad pura con el mismo modelo: una segunda corrida de Gemini 2.5 Flash
Lite fue bloqueada por la cuota gratuita observada de 20 solicitudes. Esta
limitación se documentó y no se sustituyó por datos inventados.

## Resultado de IA incorrecto o incompleto

**Prompt literal delegado al agente:**

> Construye el bloque A completo en C:\Users\carlo\Documents\Codex\2026-08-24\anal\outputs\qe-senior-ia\functional-api. Track API Karate DSL. Exactamente 4 escenarios: login válido, login inválido, búsqueda/filtro, carrito cantidad/total; contrato JSON; reusable features via call; karate-config.js por entorno; datos aislados. Incluye pom.xml, runner, schemas, instrucciones breves locales dentro de functional-api/README.md y tests/unit where possible. No toques otras carpetas. Usa apply_patch. Valida compilación si es posible con Java 21; si no hay Maven, incluye Maven Wrapper o documenta comando. No inventes resultados.

**Salida problemática.** La primera versión de `mvnw.cmd` verificaba la descarga
con `Get-FileHash`. Al ejecutar `mvnw.cmd -q -DskipTests test-compile`, el wrapper
terminó con código 1 porque ese cmdlet no estaba disponible en el shell invocado.
La generación había cubierto el camino nominal, pero no la compatibilidad real
del entorno Windows.

**Detección y corrección.** El código de salida y el mensaje
`Get-FileHash: El término 'Get-FileHash' no se reconoce` impidieron aceptar el
resultado. Se reemplazó el cmdlet por SHA-512 mediante .NET
(`[Security.Cryptography.SHA512]::Create()`, `ComputeHash` sobre un `FileStream`
y normalización con `BitConverter`). El mismo comando terminó después con código
0 y `CartTotalsTest` aprobó 2/2. La corrección conserva la verificación de
integridad; no la elimina para hacer pasar el build.

## Tarea no delegada a IA

La generación de evidencia y la decisión del gate no se delegan a una respuesta
libre de IA. Los estados provienen directamente de Karate/JUnit, CSV de Locust y
`azure-ai-evaluation`; los resultados crudos no se editan. La aprobación o
bloqueo la calcula código determinista con umbrales versionados y salida distinta
de cero. Codex orquesta y explica, pero una explicación plausible no puede
convertir una prueba roja, una corrida incompleta o un 429 en evidencia aprobada.

## Auditoría del Anexo A

### 1. Aserciones que generan falsos positivos - líneas 34 a 43

**Defecto.** El parámetro `n` no se compara con el contenido del badge. `toBeTruthy()` solo prueba que existe texto. En la API, `expect(res.status()).toBeTruthy()` acepta cualquier código distinto de cero, incluidos 404 y 500.

**Consecuencia.** La suite puede quedar verde con una cantidad incorrecta en el carrito o con el servicio averiado. Es el defecto más grave porque destruye la utilidad del sistema de pruebas como señal de liberación.

**Corrección.** Convertir el badge a número y compararlo con `n`; exigir el código HTTP exacto y validar el contrato y los valores relevantes del cuerpo.

### 2. Estado global sin aislamiento ni cierre - líneas 6, 7 y 13 a 18

**Defecto.** `browser` y `page` son variables globales compartidas, no existen hooks por escenario y el navegador nunca se cierra.

**Consecuencia.** Escenarios paralelos comparten sesión y carrito, ejecuciones sucesivas heredan estado y se acumulan procesos. El resultado depende del orden.

**Corrección.** Crear un contexto y una página por escenario mediante `Before`, guardar el estado en el World de Cucumber y cerrar contexto y navegador en `After`, incluso ante fallo.

### 3. Esperas fijas - líneas 17, 24 y 30

**Defecto.** `waitForTimeout()` presupone que la aplicación responde en un tiempo arbitrario.

**Consecuencia.** En equipos rápidos agrega demora; en equipos lentos produce intermitencia. Tampoco identifica cuál condición no se alcanzó.

**Corrección.** Esperar navegación, visibilidad o estado exacto mediante locators y assertions con timeout acotado, adjuntando trazas y capturas cuando expire.
