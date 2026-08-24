# Reglas del agente para QA Automation Senior con IA

## Dominio y alcance

Este repositorio valida un asistente de compras en tres frentes: API funcional de Toolshop, rendimiento de un emulador local de chat y calidad de respuestas mediante `azure-ai-evaluation`.

Stack permitido:

- Karate DSL y Java 21 para automatización funcional.
- Python y Locust para carga.
- `azure-ai-evaluation` para Groundedness y Relevance.
- GitHub Actions para pruebas reproducibles que no consuman modelos.

No introducir Playwright, Cucumber, otro motor de carga ni un SDK sustituto de Azure AI Evaluation.

## Convenciones

- Mantener exactamente cuatro escenarios funcionales de negocio.
- Separar configuración, datos, ejecución y aserciones.
- Generar identificadores únicos por escenario; ninguna prueba depende del orden.
- Las aserciones deben comprobar valores esperados, no solo existencia o truthiness.
- Toda espera debe estar asociada a una condición observable y tener plazo máximo.
- Los scripts deben fallar cerrados ante resultados ausentes, vacíos o no parseables.
- Los resultados publicados deben provenir de ejecuciones reales y conservar parámetros y versiones.

## Restricciones obligatorias

- Nunca escribir, imprimir, commitear ni copiar credenciales o tokens.
- Fijar el SUT por commit e integridad; no ejecutar el workflow funcional contra
  la instancia pública compartida.
- Nunca ejecutar carga contra Toolshop, el proveedor del modelo o un tercero; solo contra `localhost` o un destino expresamente autorizado.
- Nunca ejecutar la saturación completa en CI.
- Nunca llamar al modelo desde CI; CI solo relee resultados versionados.
- Nunca fabricar capturas, métricas, reportes o estados de pipeline.
- No modificar el PDF fuente ni los resultados crudos de una ejecución.
- No relajar un umbral para hacer pasar una corrida sin documentar la razón y la evidencia.

## Confirmación requerida

El agente debe pedir confirmación antes de:

- cambiar un destino de carga fuera de `localhost`;
- publicar el repositorio, invitar colaboradores o enviar la entrega;
- reemplazar evidencias finales ya versionadas;
- habilitar facturación o crear recursos de pago.
