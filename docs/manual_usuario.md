# Manual del ingeniero geotécnico

## Flujo operativo de escenarios · Fase C

Para un análisis nuevo usa los botones de Inicio **Nuevo escenario · John Henry** o **Nuevo escenario · CSV externo**. Sigue la franja de etapas: preparar/validar, visualizar, analizar, pronosticar, revisar y reportar. El escenario permanece seleccionado al navegar; el caso histórico conserva sus pantallas como referencia independiente. El menú Prismas corresponde al análisis del escenario nuevo.

La [demostración integral](demostracion_integral.md) contiene los pasos exactos. Las [reglas científicas](scientific_integration.md) explican requisitos, cortes y limitaciones. Las secciones de episodios y exportaciones CSV de este manual describen el **caso histórico**; los escenarios nuevos tienen revisión propia y reportes HTML/JSON/PDF, con trazabilidad y datos separados. Las decisiones propias se guardan en un [registro independiente](scenario_review_storage.md).

## Guardar y recuperar escenarios · Fase D.1

Abre **Escenarios guardados · Nuevo / Guardar / Abrir** en la barra lateral. Tras generar John Henry o importar un CSV, escribe un nombre y pulsa **Guardar escenario**. Se conserva una versión con mediciones, malla/configuración/semilla, corte, resultados científicos ya ejecutados y referencias de revisión. Las revisiones humanas también permanecen en su registro independiente.

Después de cerrar sesión o reiniciar, autentícate con el mismo usuario, selecciona el nombre en **Abrir escenario existente** y pulsa **Abrir escenario**. No se regeneran instrumentos ni se ejecutan modelos para abrirlo. Para visualizar John Henry se necesitan los activos locales originales verificados; una malla diferente invalida su visualización. **Nuevo escenario** limpia el trabajo temporal; los guardados siguen disponibles. Guardar otra vez añade una versión; una sesión obsoleta debe abrir la versión actual antes de actualizarla.

## Reportes guardados · Fase D.1

En **Reportes → Nuevo reporte**, revisa el resumen, escribe conclusiones obligatorias y observaciones opcionales, y pulsa **Guardar reporte**, la única acción principal de ese formulario. También se guarda una versión del escenario activo externo/John Henry. El reporte recibe un código, especialista, fecha UTC, escenario/versión y copia de resultados y decisiones disponibles. Solo después de confirmar la escritura se limpian los campos, se abre **Historial de reportes**, se restablecen sus filtros y se selecciona la edición recién guardada. Ante error se conserva el borrador. Las descargas están en el historial, después de archivar.

El historial permanece disponible aunque todavía no hayas abierto un escenario. Busca por nombre de escenario, prisma o estado y filtra las fechas. Selecciona un código y pulsa **Ver detalle**, **Descargar HTML guardado**, **Descargar JSON guardado** o **Descargar PDF guardado** sin volver a ejecutar IA. El PDF contiene identificación, conclusiones, observaciones, procedencia, último score archivado por prisma, cuantiles, métricas, revisiones y trazabilidad; el JSON conserva todos los registros originales. **Crear nueva versión del reporte** prepara otro formulario vinculado al original; abre antes el escenario que quieras revisar. El original conserva su contenido. El historial muestra únicamente reportes del usuario autenticado. El caso histórico conserva además sus exportaciones PDF/CSV/JSON en un apartado secundario del historial.

La recuperación local requiere conservar el mismo almacenamiento de runtime y la clave de la instalación. No garantiza persistencia en Render: la configuración actual del repositorio usa almacenamiento temporal y muestra un aviso. Consulta [instalación y persistencia](manual_instalacion.md); no se ha desplegado ni contratado almacenamiento duradero.

## Acceso

Ingresa usuario y contraseña; después valida TOTP. Al primer acceso configura el autenticador, guarda los diez códigos y cambia la contraseña temporal. Los códigos TOTP utilizados no se pueden repetir; cada recuperación es de un solo uso. La sesión expira tras 15 minutos sin interacción.

## Revisión

El Inicio resume resultados calculados desde los archivos y las revisiones registradas. La bandeja organiza **episodios**, con pestañas para candidatos híbridos, todos los episodios, las 34 marcas no seleccionadas, interrupciones, pendientes y revisados. Las marcas excluidas se muestran como registros individuales para conservar su trazabilidad. Los filtros de episodio no eliminan ni restringen la pestaña de marcas excluidas; esta conserva acceso al conjunto completo.

Selecciona un episodio en Abrir episodio. Revisa mediciones, marcas, scores, calidad y explicaciones. El resumen final, máximos y duración son retrospectivos; la tabla causal conserva la información disponible en cada registro. Los scores del periodo de entrenamiento también son retrospectivos. La coincidencia de métodos no confirma una condición física.

Completa estado, relevancia, comentario técnico, comentario de calidad y seguimiento. Revisor y hora se obtienen de la sesión. Para marcar Revisado se exige comentario. Cada guardado conserva versión e historial; si otro usuario modificó la revisión, recarga antes de guardar. Los estados y relevancia son **opiniones humanas**, no clasificaciones automáticas.

## Espacio, prismas y calidad

La vista histórica muestra la última posición real de cada prisma disponible hasta la fecha seleccionada. Easting, Northing y RL conservan sus valores originales; su referencia espacial no está validada contra las minas externas. El modo 2D permite seleccionar puntos; en 3D usa el selector vinculado, rotación y zoom. La serie vinculada respeta el corte temporal. Los terrenos reales de Century y John Henry están separados; en John Henry los instrumentos y mediciones son simulados. La TIN instrumental es exploratoria, no topografía certificada.

Prismas muestra movimiento, tasa derivada, scores, huecos y episodios. La aceleración no existe como campo aprobado y se informa como no disponible. `30-1994` conserva su aviso específico: solo entrenamiento, 15 evaluables marcados por ambos métodos, sin demostrar una falla. Calidad conserva los 1.280 no evaluables y sus motivos exactos. Falta de datos no es estabilidad.

## Reportes y perfil

Selecciona general, prisma o episodio; genera PDF, CSV o JSON y descarga. Los reportes incluyen advertencia, datos y revisión humana disponible. CSV protege celdas de texto frente a fórmulas de hoja de cálculo. JSON conserva firmas y valores de registros; no contiene secretos de usuarios. En perfil consulta tu historial, cambia contraseña o regenera recuperaciones con contraseña y TOTP vigente.

Los resultados requieren validación geotécnica. No uses la aplicación como autorización operativa o de seguridad.

## Vista espacial 0.7.2

Los filtros se ubican en una barra horizontal: fecha, búsqueda (pulsa Enter para aplicar), estado, solo candidatos, etiquetas, 2D/3D y limpiar. El gráfico muestra puntos originales hasta la fecha elegida. Comienza sin selección: haz clic en un punto o elige `Prisma seleccionado`. La ficha actualiza coordenadas, elegibilidad, episodios y filas candidatas al corte; el minigráfico utiliza ese mismo prisma.

`Centrar` cambia el encuadre; `Vista completa` lo restablece. Puedes rotar/zoom sin enviar eventos de auditoría. La pantalla completa aparece si el navegador la permite. `Ver historial` abre la página de ese prisma; `Revisar episodio` aparece solo si existen episodios asociados y abre uno de ellos en la bandeja. Los resúmenes de episodios siguen siendo retrospectivos, separados de los conteos al corte.

`Calidad y disponibilidad` se consulta mediante el control de información de la ficha. Allí se explica la partición y el carácter retrospectivo de las marcas de entrenamiento. El menú del usuario permite ocultar la ficha, abrir Perfil y cerrar sesión. La navegación compacta conserva los permisos por rol.

La franja topográfica informa que solo existen ubicaciones instrumentales. No se convierten coordenadas a GPS, no se infieren unidades ni se reconstruye la superficie del talud. Ausencia de datos no demuestra estabilidad.

## Sidebar compartido 0.7.3

La navegación compacta de 88 px permanece en todas las pantallas. La línea cyan identifica la opción activa. Revisión abre la bandeja y Datos abre Calidad y cobertura. El área de usuario inferior muestra el rol y abre Mi perfil; para administradores también ofrece Copias de seguridad. Salir cierra la sesión. Usuarios y Auditoría solo aparecen con permiso. En ventanas de poca altura la navegación se desplaza por separado, manteniendo el área de usuario visible.
