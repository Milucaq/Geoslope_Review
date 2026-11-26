# Instalación y recuperación

## Requisitos

Python 3.11 o posterior, laptop con navegador moderno, espacio para datos y backups. Las fases iniciales se validaron en Linux/Python 3.12; la integración científica y funcional actual se prueba en Windows/Python 3.13.14. Python 3.11 y el worker Chronos en Linux no se han revalidado en esta fase. Se recomiendan 8 GB de RAM. El checkout incluye los 17 artefactos en `ci_artifacts` y los activos topográficos optimizados; el arranque no requiere carpetas superiores ni archivos privados. Conserva por separado los datos y la clave de una instalación existente.

Chronos utiliza un entorno CPU opcional independiente, con versiones y checkpoint fijados: consulta [instalación científica](scientific_integration.md). No agregues sus pesos ni `.venv` a Git ni a la instancia gratuita de Render. Tras actualizar código reinicia Streamlit para renovar su contenedor cacheado y conserva el puerto/configuración existentes. La [demostración integral](demostracion_integral.md) usa la autenticación ya configurada.

## Windows

1. Descomprime el ZIP en una carpeta local, fuera de directorios públicos o sincronizados sin autorización.
2. Abre PowerShell en `monitoreo-taludes/geoslope_review`.
3. Ejecuta los comandos del README para crear `.venv`, activar e instalar.
4. Si PowerShell impide activar, usa directamente `.venv\Scripts\python.exe -m pip install -r requirements.txt` y el mismo ejecutable para los scripts.
5. `verify_installation.py` comprueba módulos, firmas SHA-256 y resultados aprobados antes de iniciar.
6. `initialize_database.py` crea esquema, roles e importación; no crea usuarios.
7. `run_app.bat` o `python scripts/run_app.py` inicia el servidor restringido a loopback.
8. Abre `http://127.0.0.1:8501`, crea administrador, escanea QR, valida TOTP y guarda los diez códigos mostrados una vez.
9. Crea el ingeniero y verifica ambos roles. La contraseña temporal se elige durante esa creación; no hay valor predeterminado.

## Linux/macOS

Usa `python -m venv .venv`, `source .venv/bin/activate`, `python -m pip install -r requirements.txt`, `python scripts/initialize_database.py` y `python scripts/run_app.py`.

## Offline y secretos

La instalación inicial puede requerir internet; para instalación totalmente desconectada prepara previamente wheels compatibles con el sistema. No se incluyen ruedas binarias para todas las plataformas. La aplicación, gráficos, QR, TOTP, PDF, SQLite y backups funcionan localmente. Bloquea conexiones externas si el equipo lo exige; permite loopback para Streamlit.

La clave Fernet se genera al primer inicio en `data/runtime/master.key`, nunca en el código. Puede cambiarse la ubicación mediante `GEOSLOPE_KEY_FILE` antes de iniciar. **No borres ni regeneres la clave de una instalación existente**: invalidaría las semillas TOTP cifradas y copias. Protege el archivo con ACL NTFS en Windows; en Linux se crean clave y DB con modo 0600. Protege asimismo el directorio y sus archivos WAL/SHM.

## Errores y continuidad

Dependencia faltante: instala el archivo requirements dentro de `.venv`. Artefacto alterado: no cambies el manifiesto para silenciarlo; recupera el paquete aprobado. Puerto ocupado: cierra otra instancia o usa un puerto local diferente. TOTP rechazado: revisa el reloj y espera un código nuevo; los códigos ya utilizados se rechazan. Cuenta bloqueada: espera 15 minutos o solicita desbloqueo al administrador. Si pierdes TOTP usa un código de recuperación; si pierdes además códigos y todos los administradores, conserva archivos y requiere recuperación técnica autorizada. No existe una cuenta secreta de rescate.

Para recuperar datos utiliza la pantalla de backups y la misma clave local. Antes de restaurar se genera otra copia; todas las sesiones se invalidan. Los eventos de auditoría actuales se conservan y se añaden los de la copia que faltan.

Desde Fase D.1, al iniciar se añade `workspace_records` sin reemplazar tablas existentes. Los expedientes guardados y reportes permanecen en SQLite después de reiniciar; deben abrirse con el mismo propietario desde **Escenarios guardados**. Los backups actuales incluyen también `scenario_reviews.db`; los antiguos siguen siendo compatibles y conservan los registros nuevos ausentes de su contenido. Conserva fuera de las copias SQLite los activos topográficos verificados y los modelos locales. No es necesario regenerar claves, cuentas ni instrumentos para actualizar.

## Persistencia local y Render

SQLite persiste mientras permanezcan sus archivos en el almacenamiento de la instalación. Las pruebas de reinicio y restauración de esta fase se ejecutan localmente sobre bases temporales; no demuestran durabilidad en la nube.

`render.yaml` mantiene `plan: free` sin disco persistente. `render_start.py` usa por defecto `/tmp/geoslope_review` en Linux y respeta `GEOSLOPE_RUNTIME` si el administrador ya lo configuró; cambiar la ruta no crea almacenamiento persistente. Según la [documentación oficial de Render Free](https://render.com/docs/free), los archivos locales, incluido SQLite, se pierden al reiniciar, desplegar o suspender la instancia. La interfaz muestra un aviso en Render. Una copia cifrada guardada en esa misma instancia tampoco constituye respaldo externo: debe descargarse y conservarse fuera, junto con una copia protegida separada de la clave.

Una arquitectura duradera requerirá almacenamiento persistente compatible o una base externa, así como almacenamiento estable de claves, activos y backups; debe validarse y autorizarse antes de desplegar. Esta fase no cambia el plan, no configura discos ni migra credenciales o datos a servicios externos. Véanse [discos persistentes de Render](https://render.com/docs/disks) para las condiciones de la plataforma.
