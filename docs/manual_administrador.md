# Manual del administrador

## Escenarios y revisión independiente · Fase C

Los escenarios externos y sintéticos no reemplazan el conjunto congelado ni sus dictámenes. El nuevo registro de revisión es propio de cada usuario y versión de datos; incluso el administrador no recibe decisiones ajenas por esta vía. Véase el [diseño de persistencia v1](scenario_review_storage.md).

Desde Fase D.1 los backups `.gsbackup` incluyen los escenarios/resultados/reportes de `workspace_records` y las revisiones de `scenario_reviews.db`, además del contenido histórico. Conservan cifrado y autorización administrativos. No copies archivos privados a Git. La [arquitectura opcional de inferencia](inference_architecture.md) no aprovisiona servicios y Chronos continúa separado del servidor web.

## Usuarios

Crea cuentas con nombre, usuario, rol y contraseña temporal elegida por ti. Cada persona registra su propio TOTP y cambia contraseña al primer acceso. No envíes semillas ni recuperaciones de otra persona; el sistema no las expone en la administración.

Puedes activar/desactivar, asignar rol, desbloquear, forzar cambio, restablecer TOTP o revocar todas las sesiones de una cuenta. Marca la confirmación antes de aplicar. Desactivar, cambiar rol, forzar cambio, restablecer TOTP y revocar cierran las sesiones correspondientes. El último administrador activo no puede desactivarse ni perder su rol. No existe eliminación de usuarios: sus identificadores permanecen para conservar referencias de revisión.

Restablecer TOTP genera una nueva semilla cifrada y borra recuperaciones previas; al siguiente inicio la persona debe configurar el autenticador. El administrador no ve la nueva semilla. Los intentos y sesiones se muestran sin sus tokens.

## Auditoría e integridad

Auditoría es de solo lectura y registra autenticación, bloqueos, cuentas, revisiones, importación, exportaciones, backups y configuración. Los triggers impiden modificar o borrar eventos por las rutas normales de SQL. Un administrador del sistema operativo puede alterar archivos; protege la laptop y no consideres estos triggers un registro forense certificado.

Verificar artefactos recalcula firmas SHA-256 contra el manifiesto de entrega y registra el resultado. El lector rechaza fuentes alteradas. La importación inicial es idempotente; no se admite reemplazar por otro dataset desde la interfaz porque los resultados y decisiones están congelados. Para un nuevo conjunto se necesita una fase aprobada y migración explícita; no edites hashes para forzar compatibilidad.

La única configuración modificable desde Usuarios es la preferencia no analítica de presentación. Marca, subtítulo, versión y paleta se centralizan en `config/app_config.yaml`; los valores analíticos no son editables.

## Backups

La tabla `workspace_records` se crea de forma aditiva al iniciar la aplicación actualizada; no cambia columnas ni credenciales existentes. Los escenarios y reportes se añaden por versiones desde los servicios y sus guardados generan auditoría. Las consultas aplican propietario incluso para administradores; el respaldo administrativo cubre todos los propietarios.

Se aceptan copias históricas de esquema 1 sin los campos nuevos: restaurarlas conserva la tabla de expedientes actual y no elimina revisiones independientes. Una copia actual restaura la tabla incluida a su instantánea y añade revisiones faltantes sin modificar las existentes. Se adjunta la base de revisiones a la misma conexión SQLite para su restauración con las tablas principales. La copia preventiva sigue siendo obligatoria y automática; una restauración revoca las sesiones. Los activos topográficos y pesos siguen fuera del backup y deben conservarse por separado.

Crea copias `.gsbackup` cifradas con la clave local. No incluyen sesiones. Descarga y conserva fuera del equipo junto con una copia protegida **separada** de la clave. Antes de restaurar se exige confirmación, se verifica esquema/manifiesto y se crea una copia preventiva. La restauración es transaccional, mantiene auditoría actual, recupera revisiones y revoca sesiones. No se restaura una copia sin administrador activo y TOTP configurado.

Los backups no sustituyen la copia del paquete de datos/modelos congelados; estos permanecen fuera de SQLite y se verifican por firma. Los backups contienen hashes de contraseña y TOTP cifrado dentro de un contenedor cifrado: trátalos como información confidencial.

La persistencia aquí comprobada es local, con el mismo runtime y clave. La configuración actual de Render utiliza `/tmp` y plan gratuito sin disco; reiniciar esa instancia puede perder bases, claves y backups locales. Guarda las copias fuera del servicio y revisa [las condiciones de instalación y Render](manual_instalacion.md#persistencia-local-y-render). No se ha desplegado ni habilitado persistencia en Render como parte de esta fase.
