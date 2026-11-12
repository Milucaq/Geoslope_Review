# Reporte de Arquitectura y Validación DevSecOps — HU-116

**Historia de Usuario:** `HU-116` — Reestructuración del pipeline CI en etapas visuales con diagnóstico acumulativo y seguridad ampliada  
**Rama:** `feature/HU-116-pipeline-ci-seguridad`  
**Responsable:** Carlos  
**Sprint:** Sprint 1  

---

## 1. Alcance de la Implementación

Refactorización del workflow de Integración Continua (`.github/workflows/ci.yml`) de **GeoSlope Review** para pasar de un único trabajo monolítico a una arquitectura multi-etapa (*DAG de 6 jobs*) con:
1. **Visualización en grafo dentro de GitHub Actions** mediante dependencias explícitas (`needs`).
2. **Ejecución diagnóstica no bloqueante (`if: always() && !cancelled()`)** entre la fase de análisis estático/seguridad y la fase de pruebas automatizadas, permitiendo detectar todos los errores de una rama en una sola corrida sin ocultamiento temprano.
3. **Compuerta de calidad acumulativa (*Quality Gate*)** que consolida el estado de las 5 etapas previas y publica una tabla ejecutiva en `$GITHUB_STEP_SUMMARY`.

---

## 2. Estructura de Trabajos (`jobs`) del Pipeline

| Etapa (`job_id`) | Nombre Visible en GitHub Actions | Herramientas y Verificaciones | Artefacto / Salida |
| :--- | :--- | :--- | :--- |
| **`code-quality`** | `1. Calidad y Estilo (Ruff)` | `ruff check --output-format=full .` + compilación de sintaxis (`compileall`) sobre `gsreview`, `app.py`, `scripts` y `tests`. | Anotaciones de estilo y sintaxis |
| **`security-audit`** | `2. Seguridad y Librerías (Bandit & pip-audit)` | Ejecución acumulada de: (1) `pip check`, (2) control de archivos sensibles prohibidos en Git (`.env`, `*.sqlite3`, `*.db`, `*.gsbackup`, `*.pem`, `*.key`), (3) SAST con `bandit -r gsreview app.py scripts -ll`, y (4) SCA de librerías con `pip_audit -r requirements.txt`. | `geoslope-security-reports` (`bandit-report.json`, `pip-audit-report.json`) |
| **`artifact-integrity`** | `3. Integridad de Artefactos (SHA-256)` | Validación criptográfica `SHA-256` de los 17 artefactos analíticos congelados mediante `scripts/verify_integrity.py`. | Verificación de inmutabilidad analítica |
| **`unit-domain-tests`** | `4. Pruebas Unitarias, Dominio y Seguridad` | Suite rápida de seguridad (`Argon2id`, `AES-GCM`, `TOTP`), importación/exportación CSV, generador sintético y tema visual (`if: always() && !cancelled()`). | `pytest-unit-results.xml` |
| **`integration-coverage`** | `5. Integración, UI y Cobertura (>= 90%)` | Suite completa de integración, visor espacial 3D, `AppTest` de interfaz y umbral obligatorio `--cov-fail-under=90` (`if: always() && !cancelled()`). | `geoslope-test-results` (`pytest-results.xml`, `coverage.xml`) |
| **`quality-gate`** | `6. Compuerta de Calidad (Resumen Acumulado)` | Consolida el resultado de las 5 etapas previas, genera la tabla en `$GITHUB_STEP_SUMMARY` y bloquea el merge si al menos una etapa falló. | Tabla ejecutiva en *Summary* |

---

## 3. Matriz de Verificación de Criterios de Aceptación

| ID Caso | Criterio Evaluado | Verificación Técnica | Estado |
| :--- | :--- | :--- | :---: |
| **CP-HU116-01** | **Renderizado del grafo de 6 etapas en GitHub Actions** | Las dependencias `needs` conectan las 3 etapas paralelas de la Fase 1 con las 2 etapas de pruebas de la Fase 2 y la compuerta final de la Fase 3. | ✅ Aprobado |
| **CP-HU116-02** | **Acumulación de errores sin corte prematuro** | Los bloques internos de `code-quality` y `security-audit` acumulan sus códigos de salida (`errors=$((errors + 1))`), y los jobs de pruebas usan `if: always() && !cancelled()`. | ✅ Aprobado |
| **CP-HU116-03** | **Seguridad de librerías, código e higiene Git** | Se auditan vulnerabilidades CVE (`pip-audit`), código fuente (`Bandit`), conflictos (`pip check`) y ausencia de secretos/bases de datos en Git (`git ls-files`). | ✅ Aprobado |
| **CP-HU116-04** | **Publicación de artefactos y tabla en `$GITHUB_STEP_SUMMARY`** | Se exportan `geoslope-test-results` y `geoslope-security-reports` y el job `quality-gate` escribe el resumen Markdown consolidado. | ✅ Aprobado |
