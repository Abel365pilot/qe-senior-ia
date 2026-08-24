# Resumen de ejecución Locust

- Perfil: `control`
- Generado (UTC): `2026-08-24T22:22:35.177423+00:00`
- Solicitudes: 467
- Fallos: 210 (44.968%)
- Throughput intentado: 5.658 req/s
- Latencia: p50=4700.0 ms, p95=13000.0 ms, p99=13000.0 ms
- Rango: 0.905 a 23505.307 ms
- Máximo de usuarios observado: 40
- p95 base/máximo: 1200.0 / 13000.0 ms
- Pico de throughput intentado/exitoso: 24.2 / 3.3 req/s
- Primer fallo: {'timestamp': 1787610076, 'elapsed_seconds': 55, 'users': 40, 'p95_ms': 13000.0, 'total_requests': 172, 'total_failures': 4}
- Primer error acumulado >5%: {'timestamp': 1787610077, 'elapsed_seconds': 56, 'users': 40, 'p95_ms': 13000.0, 'total_requests': 202, 'total_failures': 31}
- Primer p95 >5 000 ms: {'timestamp': 1787610031, 'elapsed_seconds': 10, 'users': 40, 'p95_ms': 5200.0, 'total_requests': 29, 'total_failures': 0}
- Primer p95 >=2x baseline: {'timestamp': 1787610025, 'elapsed_seconds': 4, 'users': 20, 'p95_ms': 2600.0, 'total_requests': 12, 'total_failures': 0}
- Nota: los cambios de User Count posteriores al fin pertenecen al drenaje; no se interpretan como niveles de carga.

Los 429 válidos cuentan como fallos de capacidad. La latencia agregada mezcla respuestas 200 encoladas con 429 rápidos; el porcentaje de error debe interpretarse junto con p95/p99.
