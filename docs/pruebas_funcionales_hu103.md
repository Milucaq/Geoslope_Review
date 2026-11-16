# Reporte de Pruebas Funcionales y Técnicas — HU-103

**Historia de Usuario:** `HU-103` — Generación de datos sintéticos de monitoreo de taludes  
**Rama:** `feature/HU-103-datos-sinteticos`  
**Responsable:** Carlos  
**Sprint:** Sprint 1  

---

## 1. Alcance de la Validación

Verificar que el módulo de generación de datos sintéticos (`gsreview/analytics/synthetic.py`), su servicio de aplicación (`gsreview/application/synthetic.py`) y su panel interactivo en la vista **Calidad de datos** (`gsreview/presentation/views.py`) cumplan con los criterios de aceptación funcionales, geotécnicos y de seguridad del proyecto **GeoSlope Review**.

---

## 2. Matriz de Casos de Prueba Funcionales

| ID Caso | Escenario / Criterio Evaluado | Entrada de Prueba | Resultado Esperado | Resultado Obtenido | Estado |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **CP-HU103-01** | **Reproducibilidad mediante semilla** | `n_prisms=10`, `days=12`, `cadence_hours=12`, `seed=103` (2 ejecuciones consecutivas) | Los DataFrames `records` y `episodes` generados en ambas ejecuciones son idénticos celda por celda. | Coincidencia exacta (`rows.equals(second["records"]) == True`). | ✅ Aprobado |
| **CP-HU103-02** | **Validación de parámetros fuera de rango** | `n_prisms` $\in \{2, 50\}$, `days` $\in \{1, 120\}$, `cadence_hours=8`, `deformed_fraction` $\in \{-0.1, 1.5\}$, `noise_mm=0.01` | Se rechaza la configuración con excepción `ValidationError` descriptiva antes de ejecutar el cálculo. | Se lanza `ValidationError` en los 8 casos límite probados. | ✅ Aprobado |
| **CP-HU103-03** | **Simulación de regímenes geotécnicos y umbrales q99** | `deformed_fraction=0.30`, umbrales congelados `BASELINE_Q99=4.4398` e `IFOREST_Q99=0.5873` | Los prismas deformados superan ambos umbrales `q99`, activan `candidate_hybrid=True` y crean episodios `SYN-EP-*`. | 100 % de los candidatos híbridos superan ambos umbrales `q99` con estado `candidato_revision`. | ✅ Aprobado |
| **CP-HU103-04** | **Cálculo de tasa de movimiento ante mediciones no evaluables** | Serie con `insufficient_history` ($t_0$) y `missing_measurement` (hueco intermedio) con `cadence_hours=12` | En filas no evaluables, `movement_rate_mm_per_day` y scores son `NaN`. En la siguiente medición válida tras un hueco, la tasa divide el desplazamiento entre el tiempo real transcurrido desde la última medición válida (`24.0 h` = `1.0 día`). | `hours_since_previous_observation == 24.0` y tasa calculada sobre el intervalo real acumulado sin sesgo por hueco. | ✅ Aprobado |
| **CP-HU103-05** | **Control de acceso, integridad y auditoría** | Llamada a `SyntheticService.generate` con token inválido y luego con sesión válida de administrador | Token inválido lanza `AccessDenied`. Sesión válida registra evento `synthetic_data_generated` en `audit_log` y mantiene intactos los 17 artefactos congelados. | `AccessDenied` verificado; evento registrado con `seed:77`; `reader.verify() == 17`. | ✅ Aprobado |
| **CP-HU103-06** | **Visualización en interfaz (Calidad de datos)** | Navegación a `Datos` $\rightarrow$ `Simulación sintética de monitoreo (HU-103)` y envío del formulario | Se renderizan 4 indicadores de resumen, gráfico de línea interactivo de desplazamiento 3D acumulado y tabla de vista previa sin errores de Streamlit. | Renderizado verificado en local y mediante `AppTest` en `test_phase7_ui.py`. | ✅ Aprobado |

---

## 3. Ejecución de Pruebas Automatizadas

Comando ejecutado:
```bash
python -m pytest -v tests/test_hu103_synthetic.py
```

Resultados obtenidos:
- `test_synthetic_generation_reproducibility_and_schema` — **PASSED**
- `test_movement_rate_with_ineligible_measurements_uses_actual_elapsed_time` — **PASSED**
- `test_synthetic_config_rejects_invalid_parameters` (8 parametrizaciones) — **PASSED**
- `test_synthetic_service_requires_auth_and_logs_audit` — **PASSED**

**Total HU-103:** `11 passed` (Suite global del repositorio: `99 passed`).
