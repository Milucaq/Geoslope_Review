# Arquitectura opcional de inferencia independiente

No se creó, contrató ni desplegó infraestructura. Se mantiene `render.yaml` y Chronos local continúa bloqueado bajo Render.

El adaptador existente `LocalChronos.predict_many(jobs)` define la frontera: hasta cuatro prefijos escalares y sus horizontes en pasos → cuantiles `[q10,q50,q90]` por paso y trazabilidad del runtime. El proceso web conserva autenticación, permisos, selección de datos, cortes temporales, referencias, métricas, revisiones y reportes. El worker conoce únicamente magnitudes, pasos y la versión fija del modelo; no recibe tokens del usuario, TOTP, nombres, coordenadas ni acceso a SQLite.

La opción futura es un proceso/servicio privado con un checkpoint verificado cargado una vez, cola acotada y concurrencia inicial 1. El backend web podría incorporar un adaptador remoto con el mismo contrato, sin cambios en fórmulas ni vistas. Antes de habilitarlo se requiere autorización para transmitir mediciones y un diseño de autenticación entre servicios, TLS, control de acceso, ausencia de payloads en logs, retención, cancelación, límites de contexto/batch, timeout y manejo de errores. La cola no debe mezclar ni reutilizar resultados entre usuarios o versiones de datos.

Para dimensionar: medir RSS/pico en Linux con contextos y horizontes máximos, arranque, latencia p95, peticiones simultáneas y recuperación tras error. El experimento Windows (~773 MiB, contextos pequeños) ya supera la RAM de la instancia gratuita configurada (512 MB); no autoriza inferir que otro tamaño o costo será suficiente. Se deben presupuestar pesos, librerías, activaciones, sistema, concurrencia y margen; validar costos y persistencia del checkpoint antes de elegir un plan.

No se añadieron endpoints públicos, clientes de terceros, variables secretas, aprovisionamiento ni fallback que simule Chronos. Cuando el worker no está listo se informa y se pueden ejecutar explícitamente las dos referencias. Resultados existentes conservan fecha/modelo; no se presentan como una nueva inferencia.
