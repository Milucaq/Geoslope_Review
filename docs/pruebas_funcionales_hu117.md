# Evidencia de Pruebas Funcionales — HU-117

## 1. Descripción General
Este documento registra la verificación funcional y automatizada de la historia de usuario **HU-117: Visualización espacial y detección de fallas en escenarios sintéticos de taludes**.

## 2. Funcionalidades Implementadas
1. **Clasificador híbrido de detección de fallas (`classify_synthetic_prisms` en `gsreview/analytics/synthetic.py`)**:
   - Evalúa por cada prisma del escenario sintético la velocidad máxima y actual (`mm/día`), la aceleración cinemática (`mm/día²`), la persistencia de marcas híbridas y los puntajes estadísticos respecto a los umbrales $q_{99}$ de **Baseline** ($4.4398$) e **Isolation Forest** ($0.5873$).
   - Calcula un índice de riesgo compuesto (`0` a `100`) y clasifica automáticamente cada punto instrumental en tres estados:
     - **Alerta de falla potencial (`alerta_falla`)**: Deformación progresiva detectada por consenso estadístico e IA.
     - **Variación en observación (`observacion`)**: Anomalía transitoria o velocidad moderada que requiere seguimiento.
     - **Normal / Estable (`estable`)**: Variaciones dentro de la banda base de ruido instrumental.
2. **Visor espacial interactivo 2D y 3D (`synthetic_spatial_map` en `gsreview/presentation/charts.py`)**:
   - Representa los prismas en sus coordenadas espaciales (`easting`, `northing`, `rl`) junto con la superficie geométrica de referencia del talud en 3D.
   - Codifica visualmente los puntos por nivel de riesgo (rojo crítico `#EF4444`, ámbar preventivo `#F59E0B`, verde estable `#10B981`) manteniendo la estética oscura instrumental del visor de GeoSlope Review.
3. **Panel de resumen ejecutivo, ficha de diagnóstico predictivo y exportación CSV (`_render_synthetic_panel` en `gsreview/presentation/views.py`)**:
   - Indicadores globales: prismas estables, en observación, alertas de falla e índice porcentual de estabilidad global del talud.
   - Controles para alternar entre vista `3D` y `2D`, filtrar por nivel de riesgo e inspeccionar la ficha técnica y el dictamen de IA de cada prisma.
   - Botón integrado para descargar las mediciones sintéticas en formato CSV 100 % compatible con el validador de importación externa (`HU-106` / `HU-111`) y el visor de datos externos (`HU-110`).

## 3. Casos de Prueba Automatizados (`tests/test_hu117_synthetic_spatial_ai.py`)

| ID Caso | Escenario de Prueba | Resultado Esperado | Estado |
| :--- | :--- | :--- | :--- |
| **CP-117-01** | Clasificación de prismas sintéticos en niveles de riesgo y cálculo de estabilidad global | Detección exacta de prismas con deformación progresiva como `alerta_falla` (`risk_score >= 75`) | **PASÓ** |
| **CP-117-02** | Validación de entradas vacías en clasificador espacial y exportador CSV | Lanzamiento controlado de `ValidationError` con mensaje descriptivo | **PASÓ** |
| **CP-117-03** | Generación de figuras espaciales 2D y 3D con simbología por riesgo y resaltado de prisma | Trazas `Scatter3d`/`Surface` en 3D y `Scatter` en 2D con paleta cromática oficial | **PASÓ** |
| **CP-117-04** | Compatibilidad del CSV sintético exportado con `validate_csv` y `prepare_external_points` | Validación exitosa de los registros exportados y bloqueo ante sesión no autorizada | **PASÓ** |
| **CP-117-05** | Renderizado en interfaz Streamlit (`Calidad de datos`) e integridad de artefactos congelados | Visualización sin excepciones de controles, mapa, ficha IA y preservación de los 17 artefactos | **PASÓ** |
