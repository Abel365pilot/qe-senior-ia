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
  por entorno; `karate-config.js` concentra tiempos, credenciales y `runId`.
- `CartTotals`: cálculo monetario determinista con pruebas unitarias.

El entorno objetivo es local (`http://localhost:8091`). El entorno `public` se
incluye solo para diagnóstico puntual; no debe usarse como sustituto de la
ejecución final porque comparte estado con terceros.

## Prerrequisitos

1. Java 21.
2. Toolshop local iniciado desde el repositorio oficial:

   ```powershell
   docker compose -f docker-compose.prod.yml up --pull missing -d
   ```

3. Definir las credenciales del usuario sembrado en la instancia local sin
   guardarlas en archivos ni en Git:

   ```powershell
   $env:TOOLSHOP_USER_EMAIL = Read-Host 'Email Toolshop'
   $env:TOOLSHOP_USER_PASSWORD = Read-Host 'Password Toolshop' -MaskInput
   ```

No se versiona ninguna credencial. `TOOLSHOP_BASE_URL` es opcional y permite
sobrescribir la URL del entorno.

El helper de login está marcado `@report=false` para que el cuerpo con la
contraseña no se incorpore al reporte HTML.

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
quedan en `target/surefire-reports/`.

## Aislamiento y contratos

- El login negativo usa un email único `example.invalid`; no acumula intentos
  fallidos sobre la cuenta válida ni puede bloquearla.
- El catálogo es de solo lectura.
- El escenario del carrito crea un ID nuevo y lo elimina al final. Si una
  aserción corta la limpieza, ese ID sigue siendo exclusivo y no interfiere con
  ejecuciones posteriores.
- Se excluye `Thor Hammer`, cuya regla de negocio impide cantidad mayor que uno.
- La API de carrito no publica un campo `total`; la prueba verifica precio y
  cantidad recibidos y calcula el total aplicando descuentos de línea y carrito.
- Cada respuesta valida el código HTTP y el esquema JSON publicado; se usa
  `contains` para tolerar extensiones compatibles del contrato.

Punto propenso a intermitencia: una instancia pública puede cambiar catálogo o
estado mientras corre la prueba. La mitigación es usar Docker local, datos
propios por escenario y aserciones de estado; no reintentos ciegos.
