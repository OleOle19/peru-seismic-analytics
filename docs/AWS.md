# Activar el archivo opcional en S3

La integración se verificó el 11 de octubre de 2026 en S3 (Ohio, us-east-2). Se cargaron 14 archivos públicos del catálogo USGS y se comprobó su integridad por SHA-256 y cifrado SSE-S3. La versión local también funciona sin AWS.

Para configurar el acceso en otro equipo:

1. Crea un bucket privado y conserva el bloqueo de acceso público.
2. Configura un perfil local mediante las herramientas oficiales de AWS, preferentemente con credenciales temporales o IAM Identity Center. No uses la cuenta raíz ni claves dentro del código.
3. Concede solo los permisos necesarios para cargar objetos en `peru-seismic/*` del bucket elegido.
4. Define en `.env`: `AWS_S3_BUCKET`, `AWS_PROFILE` y `AWS_REGION`.
5. Ejecuta `Actualizar-Datos.ps1 -SubirS3`.
6. Revisa los objetos originales y procesados y su cifrado SSE-S3. Añade una política de ciclo de vida si deseas limitar la retención.

El pipeline crea un prefijo por ejecución, conserva los GeoJSON originales y los CSV procesados, y usa `boto3.client('s3').upload_file`. No crea recursos ni configura permisos. El consumo de almacenamiento y solicitudes depende de las condiciones de tu cuenta; no se presupone gratuidad.

El proyecto ahora incluye una integración real verificada con AWS S3. No es necesario publicar el bucket: los archivos permanecen privados.

## Conexión temporal

Con AWS CLI v2 instalado, ejecuta `Conectar-AWS.ps1 -Bucket NOMBRE_DEL_BUCKET -Region us-east-2`. Autoriza la sesión en el navegador. El script usa `aws login` y un perfil de proceso para boto3; no guarda claves en el proyecto. Cuando la sesión caduque, vuelve a ejecutar el script.

Para futuras cargas ejecuta `Actualizar-Datos.ps1 -SubirS3`.

## Permisos limitados

`infra/s3-project-policy.json` proporciona una plantilla para una identidad IAM dedicada. Sustituye `REPLACE_WITH_BUCKET_NAME` por tu bucket. Permite listar el prefijo del proyecto, subir y leer sus objetos y abortar cargas multipartes. No concede administración del bucket ni permisos sobre otros servicios. Autoriza el inicio de sesión local por separado según el mecanismo de identidad elegido.

La sesión inicial de demostración se autenticó con la cuenta raíz. Para operación habitual utiliza una identidad IAM o federada con permisos limitados. La plantilla se entrega para revisión y no se aplica automáticamente a tu cuenta.
