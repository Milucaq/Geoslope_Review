# Reporte de Pruebas Funcionales y Evidencia de Compatibilidad — HU-107

**Historia de Usuario:** `HU-107` — Exportación de datos sintéticos en formato CSV  
**Rama:** `feature/HU-107-exportacion-csv`  
**Dependencia directa:** `HU-103` (Generación de datos sintéticos) y `HU-106` (Carga y validación de archivos CSV)  
**Responsable:** Carlos  
**Sprint:** Sprint 1  

---

## 1. Alcance de la Validación

Verificar que la funcionalidad de exportación de mediciones sintéticas (`export_synthetic_records_to_csv` en `gsreview/analytics/synthetic.py`, `SyntheticService.export_csv` en `gsreview/application/synthetic.py` y el botón de descarga en `_render_synthetic_panel` de `gsreview/presentation/views.py`) genere archivos CSV válidos, descargables desde la interfaz y 100 % compatibles con el validador de importación externa (`validate_csv` en `gsreview/application/csv_import.py`), sin modificar los 17 artefactos congelados del sistema.

---

## 2. Esquema CSV Coordinado (HU-106 + HU-107)

El archivo exportado codificado en `UTF-8` incluye las siguientes 9 columnas en orden estricto:

| Columna | Tipo / Formato | Requerida por HU-107 | Requerida por HU-106 (`validate_csv`) |
| :--- | :--- | :---: | :---: |
| `source_record_id` | Entero / Identificador único (`900002`, ...) | — | ✅ |
| `prism_id` | Texto no vacío (`SYN-W01` .. `SYN-W12`) | ✅ | ✅ |
| `timestamp` | Fecha/hora ISO-8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`) | ✅ | ✅ |
| `easting` | Flotante finito (`m`) | ✅ | ✅ |
| `northing` | Flotante finito (`m`) | ✅ | ✅ |
| `rl` | Flotante finito (`m`) | ✅ | ✅ |
| `reported_3d_movement_mm` | Flotante finito (`mm`) | ✅ | — |
| `movement_rate_mm_per_day` | Flotante finito (`mm/día`) | — | ✅ |
| `elapsed_hours` | Flotante finito no negativo (`>= 0`) | — | ✅ |

> **Nota técnica:** Durante la exportación se filtran automáticamente las filas con `model_eligible = False` (observación inicial `insufficient_history` y huecos instrumentales `missing_measurement`), garantizando que la totalidad de los registros exportados posea identificadores, marcas temporales UTC y valores numéricos finitos válidos.

---

## 3. Muestra del Archivo CSV Exportado (`docs/ejemplo_mediciones_sinteticas_hu107.csv`)

Parámetros del escenario por defecto (`seed=42`, `n_prisms=12`, `days=15`, `cadence_hours=12`, `deformed_fraction=0.25`, `noise_mm=0.35`):
- **Registros totales simulados:** `372`
- **Registros evaluables exportados al CSV:** `356`
- **Prismas incluidos:** `12` (`SYN-W01` a `SYN-W12`)
- **Tamaño del archivo:** `30 119 bytes` (`~29.4 KB`, muy por debajo del límite de `10 MB` de HU-106)

Primeras filas del archivo generado:
```csv
source_record_id,prism_id,timestamp,easting,northing,rl,reported_3d_movement_mm,movement_rate_mm_per_day,elapsed_hours
900002,SYN-W01,2025-01-01T12:00:00Z,1420.3659,4878.7517,280.3001,0.3652,0.7304,12.0
900003,SYN-W01,2025-01-02T00:00:00Z,1420.3657,4878.7518,280.3002,0.1257,0.479,24.0
900004,SYN-W01,2025-01-02T12:00:00Z,1420.3659,4878.7516,280.3001,0.473,0.6946,36.0
900005,SYN-W01,2025-01-03T00:00:00Z,1420.3657,4878.7518,280.3002,0.1684,0.6092,48.0
900006,SYN-W01,2025-01-03T12:00:00Z,1420.3657,4878.7518,280.3002,0.1394,0.058,60.0
```

---

## 4. Matriz de Casos de Prueba Automatizados (`tests/test_hu107_csv_export.py`)

| ID Caso | Escenario / Criterio Evaluado | Resultado Esperado | Estado |
| :--- | :--- | :--- | :---: |
| **CP-HU107-01** | **Estructura de columnas y compatibilidad directa con HU-106** | El CSV exportado incluye `prism_id`, `timestamp`, `easting`, `northing`, `rl`, `reported_3d_movement_mm`, `source_record_id`, `movement_rate_mm_per_day` y `elapsed_hours`, sin valores `NaN`, y `validate_csv(csv_bytes)` retorna las `N` filas evaluables sin excepción. | ✅ Aprobado |
| **CP-HU107-02** | **Exportación desde DataFrame prefiltrado sin columna `model_eligible`** | Exporta correctamente las filas válidas y supera `validate_csv(csv_bytes)`. | ✅ Aprobado |
| **CP-HU107-03** | **Rechazo de entradas inválidas o corruptas (9 parametrizaciones)** | Lanza `ValidationError` ante DataFrame vacío, columnas faltantes, ausencia de filas evaluables, `prism_id` vacío, `source_record_id` duplicado, `timestamp` inválido, par `(prism_id, timestamp)` duplicado, valores numéricos `NaN` o `elapsed_hours < 0`. | ✅ Aprobado |
| **CP-HU107-04** | **Seguridad, auditoría e integridad de artefactos en `SyntheticService.export_csv`** | Rechaza tokens inválidos con `AccessDenied`, registra evento `synthetic_csv_exported` en `audit_log` con detalle de filas y bytes, y mantiene intactos los 17 artefactos congelados (`app.reader.verify() == 17`). | ✅ Aprobado |
| **CP-HU107-05** | **Renderizado del botón de descarga en la interfaz (`Calidad de datos`)** | `AppTest` verifica que `_render_synthetic_panel` en `gsreview/presentation/views.py` renderiza el botón de descarga CSV sin excepciones y que `session_state["synthetic_scenario"]["csv_bytes"]` es aceptado por `validate_csv`. | ✅ Aprobado |

---

## 5. Ejecución de Pruebas Automatizadas y Cobertura

Comando ejecutado:
```bash
python -m pytest -v tests/test_hu103_synthetic.py tests/test_csv_import.py tests/test_hu107_csv_export.py --cov=gsreview.analytics.synthetic --cov=gsreview.application.synthetic --cov-report=term-missing
```

Resultado:
- `tests/test_hu103_synthetic.py`: `11 passed`
- `tests/test_csv_import.py`: `8 passed`
- `tests/test_hu107_csv_export.py`: `13 passed`
- Cobertura en `gsreview/analytics/synthetic.py`: **100 %** (`175/175` sentencias)
- Cobertura en `gsreview/application/synthetic.py`: **100 %** (`31/31` sentencias)
