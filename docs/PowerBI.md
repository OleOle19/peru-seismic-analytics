# Abrir y explorar el informe

1. Abre `powerbi/Seismic.pbip` con Power BI Desktop.
2. Si aparecen cambios pendientes del modelo, aplica los cambios.
3. Actualiza el informe. La fuente es SQL Server: servidor `localhost`, base `SeismicAnalytics`.
4. Si se solicitan credenciales, elige autenticación Windows. No necesitas una cuenta de Power BI para explorar el archivo local.
5. Si aparece un error de certificado, es una decisión de confianza para tu servidor local: revisa las opciones del diálogo. No cambies políticas globales para otros servidores.
6. Prueba el filtro de año y comprueba que cambien los indicadores y gráficas. Seleccionar una barra también filtra otras visualizaciones de la página.
7. Para entregar un archivo con datos embebidos, usa **Archivo > Guardar como > .pbix** después de actualizar. PBIP guarda definiciones y su caché local se excluye del repositorio.

## Qué estudiar

**Power Query:** las particiones usan `Sql.Database` y navegan a las tablas de SQL Server. Python realiza la limpieza del dato original; Power Query conserva la conexión reproducible y los tipos derivados de SQL. En el modo CSV se promueven encabezados y convierten tipos explícitamente.

**Modelo estrella:** `Eventos` contiene un evento por fila. Calendario, Zona y Magnitud proporcionan filtros con relaciones uno a muchos y dirección única. Esto evita relaciones ambiguas y separa descripciones de los hechos.

**Medidas y contexto:** `Eventos registrados` usa COUNTROWS; al filtrar por año o zona, el contexto determina qué filas cuenta. `Eventos M5+` usa CALCULATE y KEEPFILTERS para conservar la intersección con los filtros del usuario. `Porcentaje superficiales` usa DIVIDE para manejar un denominador cero.

**Tiempo:** Calendario contiene cada día, incluidos días sin eventos. La comparación mensual utiliza DATEADD. No interpretar la diferencia de un mes incompleto como una tendencia concluyente.

**Calidad:** las cifras de la página 3 corresponden a la última ejecución ETL y no cambian con filtros de eventos. Esa separación es intencional: describen el proceso completo de extracción.

## Si algo cambia

- Moviste la carpeta: regenera el modelo si utilizas fuente CSV.
- Cambiaste el servidor: ajusta `.env` y ejecuta `scripts/build_powerbi.py` con Power BI cerrado.
- Actualizaste datos por Python: pulsa Actualizar en Power BI; el pipeline no refresca la caché de Desktop automáticamente.
- Modificaste diseños en Desktop: no ejecutes el generador sin guardar una copia, porque reconstruye las definiciones iniciales.
