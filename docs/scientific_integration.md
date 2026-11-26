# Integración científica local de GeoSlope Review

## Alcance y límites

Estado del candidato 0.8.0: las dependencias originales del worker opcional tienen avisos de seguridad en Transformers y en la consulta upstream de PyTorch. No se instala ni habilita ese worker en Render; requiere actualización y revalidación antes de producción. Los resultados registrados corresponden al entorno original y no se sustituyen por resultados de versiones no probadas. Consulte [el informe de preparación](releases/0.8.0.md#seguridad-y-worker-opcional) antes de habilitar ese entorno experimental.

Isolation Forest detecta atipicidad estadística. Su score **no es una probabilidad de falla**. Chronos-2 pronostica exclusivamente el desplazamiento escalar reportado en mm. Ninguno clasifica estabilidad, riesgo o colapso. No se convierten magnitudes escalares en posiciones 3D ni se modifican las mediciones, episodios o dictámenes históricos.

El modelo de anomalías procede de West Wall; reproducir sus cálculos no valida su transferencia geotécnica a otras minas ni a datos sintéticos. Los estados y scores de HU-103 permanecen simulados por reglas. Los resultados calculados llevan `inference_origin=frozen_isolation_forest`, `scenario_id`, `data_origin` y versión del modelo en columnas separadas.

## Contrato de entrada

El CSV existente sigue siendo válido para visualización. Para inferencia hay que añadir **`reported_3d_movement_mm`**, magnitud escalar reportada por el instrumento en milímetros y respecto de una referencia consistente. Una celda vacía significa desconocido. Texto no numérico e infinitos se rechazan. La tasa y `elapsed_hours` del CSV se conservan para visualización, pero el modelo calcula sus propias diferencias e intervalos a partir de la serie escalar y fechas. **No integra tasas ni reconstruye desplazamientos faltantes.**

Las fechas se ordenan por prisma; IDs, fechas duplicadas e infinitos se rechazan. Las diferencias temporales se calculan en UTC; en el histórico sin zona horaria esto conserva numéricamente las duraciones, sin certificar cuál fue la zona de adquisición. No deben mezclarse referencias instrumentales cambiantes bajo un mismo ID de prisma. CRS/datum externos siguen pendientes salvo declaración y validación independientes.

Las entradas sintéticas incluyen la magnitud necesaria. El anclaje de John Henry conserva esa columna, y el modelo no usa coordenadas, amplificación de flechas ni exageración del terreno.

## Características congeladas

Orden original de `models/phase5/selected_features.json`:

| Característica | Unidad | Ventana / definición |
|---|---|---|
| movement_rate_mm_per_day | mm/día | `(x[t]-x[t-1]) / Δdías`, con ambos valores conocidos |
| local_trend_72h_slope_mm_per_day | mm/día | Pendiente OLS con tiempo real, `(t-72h,t]` |
| local_trend_7d_slope_mm_per_day | mm/día | Pendiente OLS, `(t-168h,t]` |
| historical_robust_z_score | adimensional | `(x[t]-mediana_previa)/(1.4826 × MAD_previa)`, solo `[inicio,t)` para la referencia |
| increase_proportion_72h | proporción 0–1 | Fracción de pares internos conocidos con cambio positivo, ceros en denominador |
| increase_proportion_7d | proporción 0–1 | Igual, ventana de 168 h |
| movement_72h_mad_mm | mm | MAD sin escalar de valores conocidos en 72 h |
| movement_7d_mad_mm | mm | MAD sin escalar en 168 h |
| delta_72h_absolute_sum | mm | Suma de cambios absolutos con ambos extremos dentro de la ventana |
| delta_7d_absolute_sum | mm | Igual, ventana de 168 h |
| movement_delta_mm | mm | Diferencia entre observaciones consecutivas, sin eliminar signos negativos |
| increase_streak_duration_hours | horas | Tiempo desde el inicio de la racha de incrementos conocida hasta t |
| increase_streak_count | cambios consecutivos | Cero, desconocido y hueco >72 h reinician la racha |
| local_trend_72h_r_squared | adimensional | R² de OLS en 72 h; desconocido para señal constante |
| local_trend_7d_r_squared | adimensional | R² de OLS en 168 h |
| movement_72h_range_mm | mm | Máximo menos mínimo conocidos en 72 h |
| movement_7d_range_mm | mm | Máximo menos mínimo conocidos en 168 h |

Se reutilizan las fórmulas originales de `../src/temporal_features.py` en `causal_temporal.py` (solo cambia la importación de configuración). `causal_features.py` adapta las 17 entradas y las banderas originales, sin portar funciones de entrenamiento ni depender del paquete hermano `src`.

Historia previa: ≥20 valores conocidos y ≥24 h entre los extremos previos conocidos. Ventanas suficientes: ≥3 valores, duración ≥25 % de 72/168 h, sin hueco interno >72 h. Una tendencia requiere ≥3 fechas válidas y la duración mínima; no puentea huecos entre valores válidos >72 h. MAD cero deja el z-score desconocido. Las 6 entradas indispensables y el límite de 20 % de características faltantes se toman de la configuración congelada. La imputación opcional usa exclusivamente las medianas de entrenamiento ya aprendidas; no se ajusta nada con datos nuevos.

## Confianza y reproducción

Se verifican los **17 hashes originales** antes de cargar el modelo y antes/después de inferir. Se deserializan únicamente los bytes cuyo SHA256 coincide con `models/phase5/isolation_forest.joblib` del manifiesto local. No hay API para subir modelos. La única clase original remapeada es `src.model_preprocessing.FeatureSelector`; no se importa código del directorio hermano ni se altera `sys.path` para la deserialización. La lectura usa la API de Joblib 1.5.3 fijada por la aplicación y se bloquea si difieren las versiones científicas de los metadatos.

Antes de habilitar inferencia se reconstruyen las 17 características de los 7178 registros congelados y se comparan scores, elegibilidad y marcas q99. Resultado real: error absoluto máximo de características **5.684341886080802e-14**; de scores **1.1102230246251565e-16**. Elegibilidad y marcas coinciden exactamente. Se usan `rtol=atol=1e-12`, margen pequeño para aritmética float64/lectura decimal; NaN debe coincidir y las decisiones discretas no admiten tolerancia. Cualquier discrepancia bloquea la instancia del servicio. No se reentrena ni se sobrescribe ningún artefacto.

La reproducción histórica incluye resultados retrospectivos del período de entrenamiento; no afirma disponibilidad operacional en ese período. Para nuevas inferencias, observaciones anteriores al **15 de enero de 2014** (frontera congelada) conservan score/marca desconocidos y `model_available_at_observation=False`. El contexto pasado puede contribuir a características posteriores, sin producir inferencia operacional antes de la disponibilidad del modelo.

## Chronos-2 y entorno opcional

Modelo oficial **`amazon/chronos-2`**, revisión inmutable **`29ec3766d36d6f73f0696f85560a422f50e8498c`**, licencia Apache-2.0. La revisión y hashes descargados se fijan en `config/chronos2*.json`. Los pesos usan safetensors y el runtime impide código remoto, acceso a red y cambios de revisión. Véanse la [ficha oficial de Amazon](https://huggingface.co/amazon/chronos-2) y sus [metadatos de revisión](https://huggingface.co/api/models/amazon/chronos-2).

Se comprobó instalación/importación/inferencia con Python **3.13.14 Windows**, `chronos-forecasting==2.3.2`, `torch==2.9.1+cpu`, `transformers==4.57.6`, `accelerate==1.16.0`, `einops==0.8.2`, NumPy 2.3.5 y Pandas 2.2.3. `pip check` pasó. El lock completo instalado está en `requirements-chronos-lock.txt`; `requirements.txt` de la aplicación no cambia. Las versiones soportan Python 3.13 según metadatos de PyPI y la rueda CPU comprobada. Linux/Render aún requieren su propia validación. [Distribución oficial](https://pypi.org/project/chronos-forecasting/2.3.2/).

El worker `.venv/chronos` es un proceso local separado del servidor web. Recibe solo la serie escalar, no coordenadas, usuarios ni credenciales; no contacta endpoints externos. CPU float32, dos hilos, batch 1, contexto máximo de 2048 pasos y sin aprendizaje entre prismas. Usa la [API oficial `predict_quantiles`](https://github.com/amazon-science/chronos-forecasting/blob/v2.3.2/src/chronos/chronos2/pipeline.py) con cuantiles 0.10/0.50/0.90. Se distinguen el tiempo de cálculo interno y el tiempo completo del proceso, que incluye importaciones y comprobación de hashes.

Preparación explícita; no se ejecuta en CI ni al iniciar la aplicación:

```powershell
python -m venv .venv/chronos
.venv/chronos/Scripts/python.exe -m pip install -r requirements-chronos-lock.txt
.venv/chronos/Scripts/python.exe -m pip check
python scripts/prepare_chronos2.py --download
python scripts/validate_scientific_models.py
```

Los pesos (~478 MB) y el entorno están ignorados por Git. La preparación sí necesita red; la inferencia posterior funciona offline. En Linux el ejecutable del entorno es `.venv/chronos/bin/python`.

## Evaluación temporal y política de frecuencia

Los horizontes 24/72/168 h se convierten en pasos según el intervalo **real y uniforme** de la serie. Se exige que el horizonte pueda representarse exactamente y no exceda 1024 pasos. Fechas irregulares no se convierten silenciosamente en datos regulares: se bloquea el pronóstico hasta definir y validar una política explícita de remuestreo. Los valores faltantes permanecen NaN, no se interpolan. Se requieren ≥24 fechas y ≥20 valores conocidos.

Persistencia conserva el último valor conocido y la tendencia lineal ajusta OLS al prefijo observado con posiciones temporales reales. Sus intervalos empíricos se calculan con errores de origen móvil **dentro del prefijo de entrenamiento**, por horizonte; no son intervalos calibrados garantizados. Con menos de 8 errores de calibración se conserva NaN en los extremos. La mediana de referencia sigue siendo el pronóstico puntual de cada modelo.

Validación: hasta 3 folds de origen móvil no solapados, idénticos para los modelos. No se entregan sufijos futuros al predictor ni a la calibración. MAE y RMSE usan la mediana y solo objetivos observados; la cobertura [q10,q90] usa exclusivamente pares objetivo/intervalo conocidos y registra denominadores. Si no hay folds suficientes no se inventan métricas. La columna temporal de cada fold identifica el último dato visible al modelo.

Experimento real reproducible: `reports/science/scientific_validation.json`, `synthetic_backtest.csv` y `synthetic_forecast_*h.csv`. Serie HU-103 `SYN-W01`, semilla 42, 45 días, cadencia 6 h, tres folds por horizonte. Son **resultados sobre datos sintéticos**, útiles para validar funcionamiento; no prueban desempeño geotécnico, calibración en campo ni superioridad general de Chronos. Las comprobaciones con dobles de transporte de CI no se presentan como resultados científicos.

El histórico inspeccionado (`22-1917`) tiene frecuencia irregular y queda bloqueado para pronóstico. No se ha realizado una comparación predictiva válida sobre datos de campo. Además, no se conoce si el corpus de preentrenamiento de Chronos incluyó alguna de las series públicas; no se afirma independencia respecto a ese corpus.

## Memoria, despliegue y pendientes

El experimento local midió aproximadamente **773 MiB RSS** solo en el worker. No es una prueba de carga multiusuario ni una cota máxima para contextos mayores. `render.yaml` mantiene el plan gratuito; sus **512 MB** no alcanzan para esta ejecución junto con la aplicación. [Capacidades oficiales de Render](https://render.com/docs/compute-plans).

Por ello `LocalChronos` se bloquea explícitamente si detecta Render. No se instalaron dependencias pesadas en los requisitos del servidor ni se cambió el plan. Una futura arquitectura deberá dimensionar un worker separado con memoria suficiente y concurrencia limitada, verificar Linux, almacenamiento del checkpoint, límites de tiempo y costo; cualquier servicio remoto requerirá autorización antes de transmitir datos. No se creó infraestructura ni se desplegó nada.

Pendientes: evaluación de campo con particiones y referencias instrumentales verificadas; política de frecuencia irregular; validación de transferencia del Isolation Forest; pruebas de carga/Linux; revisión visual del panel científico en navegador. La tabla científica no recolorea la escena ni sustituye la evaluación humana.

Verificación automatizada final: **233 pruebas aprobadas en 369.89 s**, cobertura global **94.75 % (2908/3069)**, sin advertencias. Ruff e integridad de los 17 artefactos aprobados; sin exclusiones ni eliminación de pruebas. Si Streamlit estaba abierto durante los cambios, reiniciarlo para renovar el contenedor cacheado antes de usar los nuevos botones científicos.

## Fase C: operación, revisión y reportes

El flujo actual conecta selección → calidad → visor → detección → pronóstico → revisión humana → reporte. Inicio muestra exclusivamente los indicadores disponibles del escenario. El histórico sigue como referencia independiente. La instrumentación y los controles de John Henry sobreviven a la navegación; el selector de escenario permanece visible en el sidebar.

La ficha de prisma enlaza geometría, última posición válida, medición, calidad, resultado real del modelo y gráfico temporal. Se preservan estados simulados y posiciones observadas; el pronóstico aparece como serie discontinua y banda q10–q90, nunca como posición futura 3D. La fecha de corte limita lo entregado a los modelos. Las métricas y versiones del análisis son del prisma/corte seleccionado.

La revisión humana se guarda en un [registro separado v1](scenario_review_storage.md), con usuario, datos, prisma, corte, análisis/modelo y versiones append-only. Hay protección frente a pestañas obsoletas y borradores entre prismas. No modifica dictámenes históricos. Desde Fase D.1 los backups cifrados incluyen ese registro y los escenarios/resultados/reportes persistentes; las copias históricas siguen aceptándose. Abrir un escenario o reporte recupera resultados archivados, sin ejecutar nuevamente los modelos ni atribuirles una nueva validación científica.

Los reportes HTML/JSON incorporan datos, procedencia, anomalías, incertidumbre, pronóstico, métricas, notas propias y limitaciones. Se escapa el HTML y se rechaza la exportación sin datos activos. La [demostración integral](demostracion_integral.md) detalla los pasos exactos.

Los resultados existentes se resumen en [experiment_summary.md](../reports/science/experiment_summary.md), con CSV de agregados/comparaciones. MAE y cobertura se ponderan por sus denominadores; el RMSE se combina a través del MSE, no promediando raíces. En este caso sintético Chronos tiene menores errores que ambas referencias en los tres horizontes; cobertura 1.00/1.00/0.666667, sin garantía del nominal 0.80 ni validación de campo. La tabla de evidencia experimental en Reportes se identifica como independiente del prisma activo.

La [arquitectura opcional](inference_architecture.md) prepara la separación de inferencia sin aprovisionar servicios ni endpoints. Chronos continúa fuera del proceso web y bloqueado localmente en Render; ausencia del worker se informa, sin simular resultados.

Verificación de Fase C: **245 pruebas integrales aprobadas en 348.96 s, cobertura medida 94.65 % (3346/3535)**, sin advertencias; 39 comprobaciones focalizadas de navegación/flujo aprobadas en 64.17 s. Ruff aprobado. La medición de cobertura se guardó en `.coverage.phase_c_final`, sin exclusiones y con umbral 90 %. Las revisiones nuevas guardan las versiones del pronóstico además de la versión de anomalías/huella del análisis. La validación visual WebGL y la evaluación de campo siguen pendientes.

Comprobación final de los últimos ajustes de trazabilidad: 11 pruebas de flujo/revisión/reportes aprobadas en 22.80 s, incluida conservación de la revisión exacta de Chronos en el contexto de la decisión.
