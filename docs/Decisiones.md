# Decisiones técnicas

## Grano y revisión de datos

Una fila representa un ID único del catálogo USGS. Las revisiones se resuelven antes de filtrar por magnitud, ubicación y periodo: una revisión nueva que ya no cumple el filtro no debe dejar vigente una versión anterior. Los registros esenciales inválidos se documentan en el control de calidad.

La extracción es un rectángulo geográfico, no una unión espacial con fronteras oficiales. Por eso el área se denomina Perú y entorno, y Norte/Centro/Sur son bandas de latitud. Una futura asignación por departamento requeriría polígonos administrativos, una regla para eventos marinos y controles de calidad espacial.

## Instantáneas frente a incrementales

El volumen actual permite reconstruir una instantánea completa. SQL Server elimina y carga los hechos dentro de una transacción, preservando el historial ETL. Esta decisión simplifica la gestión de revisiones de USGS que cambian la magnitud o ubicación.

Una carga incremental requeriría gestionar actualizaciones, eliminaciones de la fuente y eventos que entran o salen del alcance. La API limita los resultados de una consulta; se divide por años y se falla explícitamente si una respuesta puede estar truncada. Para periodos de mucha actividad se deberán usar ventanas menores.

## Consistencia entre componentes

Los CSV se preparan en una carpeta de staging y solo se publican después de una transacción SQL exitosa. Cada reemplazo de archivo es atómico, pero el conjunto de archivos no constituye una transacción distribuida con SQL Server. Un fallo de disco posterior al commit puede requerir repetir la ejecución.

La carga S3 ocurre después del procesamiento local. Un fallo remoto no revierte SQL Server. Los objetos usan un prefijo por ejecución y su contenido se compara mediante SHA-256; si algo falla, la ejecución informa el error. Actualmente no hay un mecanismo persistente de reanudación de cargas multipartes o manifiesto de estado remoto parcial.

SQL Server serializa los escritores durante la carga de la instantánea. El proyecto se ejecuta como proceso local único; ejecutar varios pipelines simultáneamente también requiere coordinar la publicación de archivos y los informes de resultados.

## Modelo analítico

Se usa un modelo estrella con dimensiones Fecha, Zona y Magnitud, y un calendario completo. Las relaciones filtran en una sola dirección. Power BI importa los datos desde SQL Server; actualizar el pipeline no refresca por sí solo la caché de Power BI Desktop.

Las medidas DAX operan sobre el contexto de filtros. Las comparaciones temporales deben considerar periodos incompletos, variaciones en tipos de magnitud y cobertura del catálogo. Las medias son descripciones del conjunto de datos, no estimaciones de energía o riesgo.

## Seguridad y nube

El repositorio excluye `.env`, credenciales, archivos de configuración local y cachés. La sesión AWS se autoriza en el navegador y boto3 utiliza un proveedor de credenciales temporales. Los objetos permanecen privados y se cifran con SSE-S3.

La plantilla IAM restringe acceso al prefijo del proyecto. Su aplicación depende de la identidad utilizada y no se automatiza como parte de una extracción. S3 es un archivo opcional de datos originales y procesados, no un paso necesario para analizar localmente.

## Mejoras futuras

- Incrementales con tratamiento explícito de revisiones y eliminación de eventos.
- Manifestación de estado por ejecución y reanudación de cargas parciales a S3.
- Orquestación y publicación de datasets con coordinación entre procesos.
- Enriquecimiento espacial con fronteras administrativas verificadas.
- Publicación del modelo en Power BI Service con refresco y permisos definidos.

Estas mejoras son propuestas; no representan funcionalidades ya implementadas.
