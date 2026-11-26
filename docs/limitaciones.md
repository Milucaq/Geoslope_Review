# Limitaciones y decisiones conservadoras

## Alcance actualizado · Fase C

El histórico sigue congelado, y ahora coexiste con CSV externos y John Henry experimental en un flujo aislado. La [documentación científica](scientific_integration.md) actualiza el alcance de inferencia y pronóstico; las menciones a nube instrumental sin topografía de las fases iniciales se refieren al histórico. Se conserva topografía real externa y se identifica explícitamente la instrumentación sintética.

Los escenarios nuevos no calculan automáticamente episodios geotécnicos ni niveles de riesgo. La revisión es humana, versionada y propia del usuario. Desde D.1 el respaldo cifrado incluye el registro separado y los escenarios/resultados/reportes guardados; el trabajo temporal requiere la acción explícita de guardar. El pronóstico solo representa una magnitud escalar en el tiempo, bloquea frecuencia irregular y no crea posiciones 3D futuras. Las métricas registradas son sintéticas y no validan desempeño de campo.

## Datos y geotecnia

Solo un conjunto histórico sin suficientes etiquetas profesionales; no se mide rendimiento sobre fallas reales. El evento del 23-feb-2014 está fuera del periodo y no configura la app. Las marcas/candidatos no son niveles de riesgo ni probabilidades. Ventana 72 h y persistencia 2 requieren validación especializada. Las 34 marcas excluidas y cuatro episodios con interrupciones siguen visibles, aunque no sean seleccionados por híbrida.

Easting, Northing y RL históricos permiten una nube instrumental 3D, pero su CRS/datum no están validados contra las minas externas. No se les asigna John Henry por proximidad aparente. La topografía externa conserva procedencia y NoData; sus pendientes son geometría, no estabilidad ni riesgo. No hay detección de grietas. La aceleración no está disponible como variable congelada y la pantalla lo informa.

Los estados de entrenamiento son retrospectivos. La agrupación de Fase 6 es causal condicionada a marcas congeladas; no representa operación en línea en cada fecha de entrenamiento. La falta de datos no demuestra estabilidad. No se unen lluvia, sismicidad o voladuras con relojes y semánticas sin validar.

## Aplicación y seguridad

Uso local por laptop; no despliegue web ni URL pública. Las revisiones son persistentes y versionadas, pero no equivalen a una gestión corporativa de expedientes. La preferencia de filas cambia la paginación de la bandeja, sin limitar el acceso al resto ni cambiar exportaciones o analítica. Se rechaza todo dataset incompatible; no existe carga libre de nuevos modelos.

La DB no está cifrada integralmente; cifrado de disco y ACL son responsabilidad de instalación. Quien controla el sistema operativo puede alterar archivos. El hash del manifiesto detecta cambios frente a esta entrega; no constituye firma de un tercero. TOTP depende de reloj correcto. La recuperación de instalaciones sin clave/recuperaciones/administradores requiere asistencia técnica autorizada; no existe bypass oculto.

La persistencia SQLite se verifica sobre almacenamiento local conservado. No implica persistencia en Render: el repositorio mantiene plan gratuito, sin disco, y runtime en `/tmp`. Los archivos locales pueden perderse al reiniciar o desplegar esa instancia. Los backups requieren conservación fuera de ella. No se ha habilitado ni validado almacenamiento duradero en la nube en esta fase.

Los reportes archivados tienen versiones independientes. El PDF es un resumen legible de esa edición, con el último score guardado por prisma y los cuantiles/métricas disponibles; no sustituye la descarga JSON con todos los registros y valores ausentes originales. Ninguna consulta o exportación de una edición ejecuta IA.

Las primeras fases se validaron en Linux/Python 3.12 y la integración actual en Windows/Python 3.13.14. El worker opcional en Linux y la carga multiusuario siguen pendientes. La instalación puede requerir red autorizada; la inferencia local de Chronos opera offline con hashes verificados.

## Mejoras futuras

Validación con especialistas y etiquetas humanas; topografía real con referencia aprobada; interoperabilidad local; instalación empaquetada Windows; revisión independiente de seguridad; migraciones versionadas para nuevas fases; pruebas de usabilidad con personas. Ninguna mejora implica reentrenar automáticamente ni cambiar umbrales sin otra fase aprobada.
