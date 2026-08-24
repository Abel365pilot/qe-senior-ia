# Automatización funcional API - Toolshop

Suite Karate DSL para los criterios de aceptación 1 a 3 del reto. Contiene
exactamente cuatro escenarios de negocio: login válido, login inválido,
búsqueda con filtro y carrito con cantidad/total.

## Diseño

- `toolshop-api.feature`: única especificación ejecutable; limita el reporte a
  cuatro escenarios.
- `helpers/*.feature`: clientes HTTP reutilizables invocados mediante `call`.
- `schemas/*.json`: contratos del OpenAPI para códigos y estructura JSON.
- `karate-config-local.js` y `karate-config-public.js`: configuración separada
  por entorno; `karate-config.js` concentra tiempos, credenciales, trazabilidad y
  limpieza defensiva.
- `RuntimeSettings`: configuración fail-fast y controles para impedir que un
  error de perfil dirija pruebas hacia un host compartido.
- `TestData`: fábrica determinista de credenciales inválidas, únicas por corrida.
- `CartTotals`: cálculo monetario con `BigDecimal`, validación de invariantes y
  pruebas de límites.

El entorno objetivo es local (`http://localhost:8091`). El entorno `public` se
incluye solo para diagnóstico puntual; no debe usarse como sustituto de la
ejecución final porque comparte estado con terceros.

## Prerrequisitos

1. Java 21.
2. Toolshop local iniciado desde el repositorio oficial:

   - Origen: `https://github.com/testsmith-io/practice-software-testing`.
   - Revisión fijada: `9e7736c3841ec2bbb9a6822c9e6602353b7b9a65` (Sprint 5).
   - OpenAPI versionado en esa revisión: `sprint5/API/storage/api-docs/api-docs.json`.
   - SHA-256 del OpenAPI: `a1b79c7e0df4ee64f3ae0fbc76401c1e2071fc5fbaa00bb8b89d482df09e9580`.

   ```powershell
   git clone https://github.com/testsmith-io/practice-software-testing.git
   cd practice-software-testing
   git checkout --detach 9e7736c3841ec2bbb9a6822c9e6602353b7b9a65
   docker compose -f docker-compose.prod.yml up --pull missing -d
   ```

3. Definir las credenciales del usuario sembrado en la instancia local sin
   guardarlas en archivos ni en Git:

   ```powershell
   $env:TOOLSHOP_USER_EMAIL = Read-Host 'Email Toolshop'
   $env:TOOLSHOP_USER_PASSWORD = Read-Host 'Password Toolshop' -MaskInput
   ```

No se versiona ninguna credencial. La suite falla antes de enviar la primera
petición si falta una credencial, el entorno no es `local|public`, la URL no es
segura o un timeout queda fuera de `1000..60000 ms`. `TOOLSHOP_BASE_URL` es
opcional; por defecto apunta a `http://localhost:8091`.

El helper de login está marcado `@report=false` y recibe las credenciales por
scope heredado, no como argumento de `call`; así el cuerpo y el `callArg` con la
contraseña no se incorporan a los artefactos Karate.

Variables opcionales:

| Variable | Uso |
|---|---|
| `TOOLSHOP_CONNECT_TIMEOUT_MS` | Conexión HTTP; `5000` por defecto |
| `TOOLSHOP_READ_TIMEOUT_MS` | Lectura HTTP; `10000` por defecto |
| `TOOLSHOP_BASE_URL` | Endpoint alternativo sin ruta, query ni credenciales |
| `TOOLSHOP_ALLOW_REMOTE=true` | Opt-in para un host no loopback con perfil local (p. ej. red Docker) |
| `TOOLSHOP_ALLOW_PUBLIC=true` | Opt-in obligatorio para el perfil público compartido |

## Ejecución

Desde esta carpeta:

```powershell
.\mvnw.cmd clean test
```

Maven no necesita estar instalado: el wrapper descarga Maven 3.9.11, valida su
SHA-512 y lo conserva en una carpeta ignorada por Git.

Para un endpoint local alternativo:

```powershell
$env:TOOLSHOP_BASE_URL = 'http://localhost:8091'
.\mvnw.cmd clean test -Dkarate.env=local
```

El reporte consultable queda en `target/karate-reports/`. Los resultados JUnit
quedan en `target/surefire-reports/`. El runner también genera Cucumber JSON,
JUnit XML y `target/karate-reports/karate-summary.json` para ingestión automática.

Las pruebas unitarias y de arquitectura no realizan llamadas HTTP:

```powershell
.\mvnw.cmd -q "-Dtest=toolshop.support.*Test" test
```

La ejecución diagnóstica contra la instancia pública exige un consentimiento
explícito y no debe emplearse para carga:

```powershell
$env:TOOLSHOP_ALLOW_PUBLIC = 'true'
.\mvnw.cmd clean test -Dkarate.env=public
```

## Aislamiento y contratos

- El login negativo usa un email único `example.invalid`; no acumula intentos
  fallidos sobre la cuenta válida ni puede bloquearla.
- Cada petición incorpora `X-QE-Run-Id`, que permite correlacionar una falla con
  la corrida sin registrar secretos.
- El catálogo es de solo lectura.
- El escenario del carrito crea un ID nuevo y lo elimina al final. Un hook
  `afterScenario` intenta una única limpieza defensiva solo cuando la ejecución
  se corta antes del borrado explícito; no se usan reintentos ciegos.
- Se excluye `Thor Hammer`, cuya regla de negocio impide cantidad mayor que uno.
- La API de carrito no publica un campo `total`; la prueba verifica precio y
  cantidad recibidos y calcula el total aplicando descuentos de línea y carrito.
- Cada respuesta valida código HTTP, `Content-Type`, esquema JSON y reglas
  semánticas (enteros positivos, descuentos válidos y campos no vacíos). Se usa
  `contains` para tolerar extensiones compatibles del contrato.
- `FeatureArchitectureTest` protege el límite de cuatro escenarios, comprueba
  que los siete clientes reutilizables se invoquen vía `call`, parsea todos los
  contratos y prohíbe sleeps o reintentos ciegos.
- `ContractSchemaTest` ejecuta los predicados de contrato contra respuestas
  representativas y demuestra que datos semánticamente inválidos son rechazados.

Punto propenso a intermitencia: entre `GET /products` y
`POST /carts/{cartId}` otro actor de una instancia compartida puede cambiar
stock, restricciones o descuentos del producto seleccionado. La señal esperada
es un status de negocio inesperado o una discrepancia en precio/descuento,
correlacionable mediante `X-QE-Run-Id` y el cuerpo de respuesta preservado. Se
mitiga con la revisión Docker fijada, base recién sembrada, carrito único y
cleanup; nunca con un retry global que oculte la carrera.
