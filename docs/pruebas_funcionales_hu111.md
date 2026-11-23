# Evidencia de Pruebas Funcionales y de Seguridad — HU-111

## 1. Descripción General
Este documento registra las pruebas funcionales y automatizadas de la historia de usuario **HU-111: Seguridad en la carga de archivos y acceso a GeoSlope Review**.

## 2. Controles de Seguridad Implementados
1. **Validación de metadatos de archivo (`validate_upload_metadata`)**:
   - Restricción estricta a extensión `.csv`.
   - Bloqueo de secuencias de *Path Traversal* (`..`, `/`, `\`) y bytes nulos (`\x00`) en el nombre del archivo.
   - Verificación de tipos MIME permitidos (`text/csv`, `application/csv`, `text/plain`).
2. **Inspección de contenido y bloqueo de binarios disfrazados (`validate_csv`)**:
   - Límite estricto de tamaño máximo de `10 MB` (`MAX_FILE_SIZE`) y `100,000` registros (`MAX_ROWS`).
   - Rechazo inmediato de archivos con bytes nulos o firmas binarias mágicas (`MZ` ejecutables Windows, `PK` comprimidos/XLSX, `%PDF`, `PNG`, `JPEG`, `ELF`).
3. **Prevención de CSV Injection (Formula Injection) y XSS**:
   - Rechazo de identificadores (`source_record_id`, `prism_id`) que comiencen con operadores de ejecución de fórmulas (`=`, `+`, `-`, `@`, `\t`, `\r`).
   - Bloqueo de patrones peligrosos (`<script`, `javascript:`, `onerror=`, `onload=`, `cmd|`, `powershell`).
   - Límite de longitud máxima de identificadores (`128` caracteres) y verificación de valores numéricos finitos (`np.isfinite`, bloqueando `inf` y `-inf`).
4. **Protección de acceso y funciones administrativas**:
   - Verificación de permisos RBAC por rol (`administrador` vs. `ingeniero`) en gestión de usuarios, sesiones, preferencias de configuración y copias de seguridad cifradas.
   - Mensajes de rechazo claros y seguros sin exposición de trazas internas, hashes Argon2id, semillas TOTP ni claves de instalación (`GEOSLOPE_SETUP_KEY`).

## 3. Casos de Prueba Automatizados (`tests/test_hu111_security.py`)

| ID Caso | Escenario Evaluado | Resultado Esperado | Estado |
| :--- | :--- | :--- | :--- |
| **CP-111-01** | Carga de archivo CSV válido con metadatos seguros | Validación exitosa y retorno de DataFrame | **PASÓ** |
| **CP-111-02** | Rechazo de extensiones peligrosas (`.exe`, `.xlsx`, `.pdf`, `.js`) y *path traversal* (`../`) | Excepción `ValidationError` con mensaje seguro | **PASÓ** |
| **CP-111-03** | Rechazo de tipos MIME no permitidos (`application/javascript`, `text/html`) | Excepción `ValidationError` por tipo MIME | **PASÓ** |
| **CP-111-04** | Rechazo de archivos binarios renombrados a `.csv` (`MZ`, `PK`, `%PDF`, `PNG`, bytes nulos) | Excepción `ValidationError` por contenido binario | **PASÓ** |
| **CP-111-05** | Rechazo de *CSV Injection / Formula Injection* (`=CMD...`, `+SUM`, `@IMPORTXML`) y `<script>` | Excepción `ValidationError` por caracteres o patrones inseguros | **PASÓ** |
| **CP-111-06** | Rechazo de identificadores que exceden 128 caracteres y coordenadas no finitas (`inf`) | Excepción `ValidationError` | **PASÓ** |
| **CP-111-07** | Rechazo de archivos que superan el límite de 10 MB | Excepción `ValidationError` de límite de tamaño | **PASÓ** |
| **CP-111-08** | Bloqueo de acceso a funciones administrativas para usuarios con rol `ingeniero` o sin sesión | Excepción `AccessDenied` | **PASÓ** |
| **CP-111-09** | Verificación de ausencia de secretos, hashes o trazas en código fuente y mensajes de error | Sin filtración de credenciales ni secretos | **PASÓ** |
