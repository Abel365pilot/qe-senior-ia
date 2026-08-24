# Resumen de ejecución Locust

- Perfil: `saturation`
- Generado (UTC): `2026-08-24T23:20:17.173026+00:00`
- Solicitudes: 1372
- Fallos: 117 (8.528%)
- Throughput intentado: 2.83 req/s
- Latencia: p50=2900.0 ms, p95=19000.0 ms, p99=19000.0 ms
- Rango: 1.15 a 19521.637 ms
- Máximo de usuarios observado: 60
- Primera muestra p95: 1200.0 ms
- p95 máximo: 19000.0 ms
- Pico de throughput intentado/exitoso: 12.5 / 3.4 req/s
- Primer fallo: {'timestamp': 1787609896, 'elapsed_seconds': 419, 'users': 40, 'p95_ms': 13000.0, 'total_requests': 1050, 'total_failures': 5}
- Primer error acumulado >5%: {'timestamp': 1787609956, 'elapsed_seconds': 479, 'users': 60, 'p95_ms': 19000.0, 'total_requests': 1339, 'total_failures': 102}
- Primer p95 >5 000 ms: {'timestamp': 1787609786, 'elapsed_seconds': 309, 'users': 20, 'p95_ms': 5200.0, 'total_requests': 700, 'total_failures': 0}
- Baseline estable: 1500.0 ms a 4 VU (median_last_30_samples)
- Primer p95 >=2x baseline estable: {'timestamp': 1787609723, 'elapsed_seconds': 246, 'users': 10, 'p95_ms': 3100.0, 'total_requests': 505, 'total_failures': 0}
- Nivel 1 usuarios: p95 final=1400.0 ms, p95 máx=1500.0 ms, éxito pico=0.8 req/s, error acum. máx=0.0%
- Nivel 2 usuarios: p95 final=1400.0 ms, p95 máx=1500.0 ms, éxito pico=1.6 req/s, error acum. máx=0.0%
- Nivel 4 usuarios: p95 final=1500.0 ms, p95 máx=1500.0 ms, éxito pico=3.1 req/s, error acum. máx=0.0%
- Nivel 6 usuarios: p95 final=2200.0 ms, p95 máx=2500.0 ms, éxito pico=3.3 req/s, error acum. máx=0.0%
- Nivel 10 usuarios: p95 final=3700.0 ms, p95 máx=3800.0 ms, éxito pico=3.3 req/s, error acum. máx=0.0%
- Nivel 20 usuarios: p95 final=6600.0 ms, p95 máx=6800.0 ms, éxito pico=3.3 req/s, error acum. máx=0.0%
- Nivel 40 usuarios: p95 final=13000.0 ms, p95 máx=13000.0 ms, éxito pico=3.4 req/s, error acum. máx=2.241%
- Nivel 60 usuarios: p95 final=19000.0 ms, p95 máx=19000.0 ms, éxito pico=3.3 req/s, error acum. máx=8.635%

Los 429 válidos cuentan como fallos de capacidad. La latencia agregada mezcla respuestas 200 encoladas con 429 rápidos; el porcentaje de error debe interpretarse junto con p95/p99.
