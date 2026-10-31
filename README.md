# Evaluación Parcial N°2: Infraestructura Serverless
## Proyecto: "Image Metadata API" en Amazon Web Services

- **Asignatura:** Infraestructura de Aplicaciones II (INY1106)
- **Estudiante:** José Villarroel
- **Carrera:** Ingeniería en Informática / Conectividad y Redes
- **Institución:** Duoc UC
- **Región AWS:** `us-east-1` (N. Virginia)
- **Cuenta AWS:** `[ACCOUNT_ID]` (AWS Academy Learner Lab)

---

## 1. Descripción y Arquitectura del Proyecto

El objetivo de esta evaluación práctica es implementar y documentar una arquitectura Serverless en Amazon Web Services que permita:
1. Subir imágenes hacia un bucket de almacenamiento escalable y seguro (**Amazon S3**).
2. Procesar y almacenar metadatos (identificador único `image_id`, URL de acceso y tamaño real en bytes `size`) en una base de datos NoSQL administrada (**Amazon DynamoDB**).
3. Recuperar dichos metadatos mediante peticiones HTTP RESTful a través de **Amazon API Gateway**.
4. Ejecutar la lógica de backend sin administración de servidores mediante funciones **AWS Lambda** desarrolladas en Python 3.12.
5. Monitorear la infraestructura, analizar logs y auditar métricas mediante **Amazon CloudWatch**.

### Diagrama de Arquitectura
![metadata api diagram](img/image_metadata_api_diagram.png)

### Flujo de la Solución
1. El cliente envía una petición HTTP `POST /upload` con los bytes de la imagen a través de **API Gateway**.
2. API Gateway invoca mediante integración tipo Proxy a la función Lambda `upload_image`.
3. La función decodifica el cuerpo (soportando Base64 si aplica), genera un identificador único alfanumérico (`image_id`), almacena el objeto binario en el bucket **S3** con `ContentType='image/jpeg'` y guarda el registro con `image_id`, `url` y `size` en la tabla **DynamoDB** (`ImageMetadata`).
4. Para consultar la información, el cliente envía una petición `GET /metadata/{image_id}` a API Gateway.
5. API Gateway invoca a la función Lambda `get_image_metadata`, la cual extrae el parámetro de ruta de forma segura, consulta la tabla **DynamoDB** por clave primaria y retorna el item serializado en formato JSON con código `200 OK` (o `404 Not Found` si el identificador no existe).

---

## 2. Paso a Paso de Implementación

### Paso 1: Creación del Bucket Amazon S3 (IE2.2.1)
- **Servicio:** Amazon Simple Storage Service (S3)
- **Nombre del Bucket:** `my-image-storage-bucket-[ACCOUNT_ID]`
- **Región:** `us-east-1`
- **Configuración de Seguridad y Almacenamiento Verificada:**
  - Cifrado en reposo: SSE-S3 (habilitado por defecto en Amazon S3).
  - Bloqueo de acceso público (Block Public Access): Activo (`BlockPublicAcls: true`, `IgnorePublicAcls: true`, `BlockPublicPolicy: true`, `RestrictPublicBuckets: true`), impidiendo accesos anónimos indebidos a nivel de bucket.
  - Versionado: Deshabilitado por defecto.

![Bucket S3](img/01_s3_bucket.png)
*Figura 1: Bucket S3 `my-image-storage-bucket-[ACCOUNT_ID]` en `us-east-1`.*

![S3 Objeto Almacenado](img/01b_s3_objects.png)
*Figura 1.1: Objeto `.jpg` almacenado en el bucket S3.*

---

### Paso 2: Creación de la Tabla DynamoDB (IE2.2.2)
- **Servicio:** Amazon DynamoDB
- **Nombre de la tabla:** `ImageMetadata`
- **Clave primaria (Partition Key):** `image_id` (Tipo: `String`)
- **Modo de Capacidad:** On-Demand (`PAY_PER_REQUEST`), escalando automáticamente según la carga de trabajo.

![DynamoDB Tabla](img/02_dynamodb_table.png)
*Figura 2: Tabla DynamoDB `ImageMetadata` con clave primaria `image_id`.*

![DynamoDB Elementos](img/02b_dynamodb_items.png)
*Figura 2.1: Metadatos registrados en DynamoDB (`image_id`, `url`, `size`).*

---

### Paso 3: Despliegue de Funciones AWS Lambda (IE2.1.1)

Se desplegaron dos funciones serverless con runtime **Python 3.12**, tiempo de espera (*timeout*) ajustado a **30 segundos** y rol de ejecución `LabRole`.

> **Nota sobre Seguridad y Permisos IAM:**  
> `LabRole` es el rol preconfigurado del Learner Lab, con permisos amplios, y se usó por restricción del laboratorio (el entorno académico bloquea la creación de roles IAM personalizados con privilegios mínimos).

#### 3.1 Función `upload_image`
- **Runtime:** Python 3.12
- **Handler:** `upload_image.upload_image`
- **Timeout:** 30 segundos
- **Rol IAM:** `LabRole` (`arn:aws:iam::[ACCOUNT_ID]:role/LabRole`)
- **Variables de Entorno:**
  - `BUCKET_NAME`: `my-image-storage-bucket-[ACCOUNT_ID]`
  - `TABLE_NAME`: `ImageMetadata`
- **Lógica implementada:** Decodificación de body binario/Base64, carga a S3 con `ContentType='image/jpeg'`, inserción de metadatos en DynamoDB y manejo de error `400 Bad Request` ante carga vacía.

![Lambda upload_image](img/03_lambda_upload.png)
*Figura 3: Configuración y variables de entorno de la función `upload_image`.*

#### 3.2 Función `get_image_metadata`
- **Runtime:** Python 3.12
- **Handler:** `get_image_metadata.get_image_metadata`
- **Timeout:** 30 segundos
- **Rol IAM:** `LabRole`
- **Variables de Entorno:**
  - `TABLE_NAME`: `ImageMetadata`
- **Lógica implementada:** Extracción resiliente de `pathParameters` (manejando `None`), consulta por `image_id`, retorno `404 Not Found` en caso de no existir y serialización JSON adecuada para campos numéricos `Decimal`.

![Lambda get_image_metadata](img/04_lambda_get.png)
*Figura 4: Configuración y variables de entorno de la función `get_image_metadata`.*

---

### Paso 4: Configuración y Despliegue de Amazon API Gateway (IE2.2.3)
- **Servicio:** Amazon API Gateway
- **Nombre de la API:** `ImageMetadataAPI` (REST API Regional)
- **Etapa de Despliegue (Stage):** `dev`
- **URL Base:** `https://[API_ID].execute-api.us-east-1.amazonaws.com/dev`

#### Endpoints Configurados:
1. `POST /upload`: Conectado a la función Lambda `upload_image` vía Integración Proxy (`AWS_PROXY`).
2. `GET /metadata/{image_id}`: Conectado a la función Lambda `get_image_metadata` vía Integración Proxy (`AWS_PROXY`), vinculando el parámetro de ruta `{image_id}`.
3. Permisos `lambda:InvokeFunction` otorgados a `apigateway.amazonaws.com` en ambas Lambdas.

![API Gateway Recursos](img/05_api_gateway.png)
*Figura 5: Estructura de recursos y métodos en API Gateway `ImageMetadataAPI`.*

![API Gateway Stage Dev](img/05b_api_stage.png)
*Figura 5.1: Stage `dev` desplegado con invocación activa.*

---

### Paso 5: Pruebas de Funcionamiento de la API (IE2.3.1)

#### 5.1 Subida de Imagen (`POST /upload`)
- **Método:** `POST`
- **Endpoint:** `https://[API_ID].execute-api.us-east-1.amazonaws.com/dev/upload`
- **Body:** Binario de imagen JPEG (524 bytes)
- **Respuesta:** `200 OK`
```json
{
  "message": "Image uploaded successfully!",
  "url": "https://my-image-storage-bucket-[ACCOUNT_ID].s3.amazonaws.com/024be46d4f384965bc7763bee511c0c9.jpg"
}
```

![Prueba POST Postman](img/06_postman_post.png)
*Figura 6: Solicitud POST /upload exitosa.*

#### 5.2 Consulta de Metadatos (`GET /metadata/{image_id}`)
- **Método:** `GET`
- **Endpoint:** `https://[API_ID].execute-api.us-east-1.amazonaws.com/dev/metadata/024be46d4f384965bc7763bee511c0c9`
- **Respuesta:** `200 OK`
```json
{
  "url": "https://my-image-storage-bucket-[ACCOUNT_ID].s3.amazonaws.com/024be46d4f384965bc7763bee511c0c9.jpg",
  "size": 524.0,
  "image_id": "024be46d4f384965bc7763bee511c0c9"
}
```

![Prueba GET Postman](img/07_postman_get.png)
*Figura 7: Solicitud GET /metadata/{image_id} retornando los metadatos de la imagen.*

---

### Paso 6: Troubleshooting y Monitoreo en CloudWatch (IE2.3.2)

#### 6.1 Análisis de Logs en Amazon CloudWatch
En los grupos de registros (`/aws/lambda/upload_image` y `/aws/lambda/get_image_metadata`) se verificó la traza real de ejecución con los reportes generados por el runtime de Lambda:

**Extracto real de ejecución en CloudWatch (`upload_image`):**
```text
REPORT RequestId: 31321f0b-b2ab-4efd-8764-0ce74418544b
  Duration: 505.51 ms
  Billed Duration: 1034 ms
  Memory Size: 128 MB
  Max Memory Used: 96 MB
  Init Duration: 528.08 ms
```

**Extracto real de ejecución en CloudWatch (`get_image_metadata`):**
```text
REPORT RequestId: 884d8143-ac5a-4b87-b055-a35a8429491e
  Duration: 39.70 ms
  Billed Duration: 40 ms
  Memory Size: 128 MB
  Max Memory Used: 90 MB
```

![CloudWatch Logs](img/08_cloudwatch_logs.png)
*Figura 8: Grupos de registro y eventos en CloudWatch Logs.*

#### 6.2 Métricas de Rendimiento en CloudWatch
Métricas reales recopiladas en CloudWatch tras el ciclo de pruebas:

| Métrica | `upload_image` | `get_image_metadata` |
|---|---|---|
| Invocaciones (Invocations) | 3 | 3 |
| Tasa de Errores no controlados (Errors 5xx) | 0 | 0 |
| Duración Promedio Warm (Duration) | ~1.51 ms | ~39.70 ms |
| Duración Cold Start (con Init) | ~505.51 ms | ~279.26 ms |
| Memoria Máxima Utilizada (Max Memory) | 96 MB / 128 MB | 90 MB / 128 MB |

![CloudWatch Métricas](img/09_cloudwatch_metrics.png)
*Figura 9: Métricas agregadas de invocaciones y duración en CloudWatch.*

#### 6.3 Error Provocado y Análisis
Como parte de las pruebas de resiliencia y troubleshooting:
- **Prueba 1 (Cuerpo vacío en subida):** Se envió una petición `POST /upload` sin cuerpo binario (`data=b''`). La función capturó la excepción `ValueError`, registrando en CloudWatch `Error de validacion: No image data received` y devolviendo al cliente un código HTTP `400 Bad Request` controlado con `{"error": "No image data received"}` en lugar de fallar con un error 500 no controlado.
- **Prueba 2 (Identificador inexistente):** Se consultó `GET /metadata/nonexistent99999`. La función verificó la ausencia del ítem en DynamoDB y retornó de forma limpia un código `404 Not Found` con `{"message": "Image not found"}`.

---

## 3. Estrategias de Optimización y Aseguramiento de Escalabilidad (IL2.3)

### 3.1 Mejoras de Rendimiento Aplicadas
1. **Reutilización de Clientes SDK fuera del Handler:**
   Los clientes `boto3.client('s3')` y `boto3.resource('dynamodb')` se inicializan fuera de las funciones `upload_image` y `get_image_metadata`. Esto permite reutilizar los sockets TCP y las sesiones TLS existentes en invocaciones subsiguientes dentro del mismo contenedor caliente (warm execution), reduciendo la latencia de `upload_image` desde ~505 ms en frío hasta ~1.5 ms en caliente.
2. **Impacto de la Memoria en Cómputo y CPU:**
   En AWS Lambda, la vCPU asignada es proporcional a la memoria RAM configurada. Las funciones están configuradas actualmente con **128 MB**. Pasar a **512 MB** asignaría 4 veces más capacidad de CPU y ancho de banda de red, lo que aceleraría el procesamiento de imágenes y la transferencia a S3, reduciendo la duración facturada.
3. **Mitigación de Arranques en Frío (Cold Starts):**
   Para entornos de producción con requerimientos de latencia estricta, la habilitación de **Provisioned Concurrency** (Concurrencia Aprovisionada) mantiene entornos de ejecución inicializados, eliminando la sobrecarga del cold start en picos de demanda.
4. **Modo On-Demand en DynamoDB:**
   La tabla opera en modo `PAY_PER_REQUEST`, lo que evita caídas por saturación de lectura o escritura (*throttling*) y elimina costos por capacidad aprovisionada no utilizada.

### 3.2 Descarga directa con S3 Pre-Signed URLs (recomendación de arquitectura, no implementada)
Actualmente, la función Lambda sube directamente la imagen a S3 y guarda la URL pública en DynamoDB. Sin embargo, dado que el bucket mantiene activo el bloqueo de acceso público (*Block Public Access*) por seguridad corporativa, los usuarios no podrán visualizar el objeto directamente desde la URL pública estándar.
Como recomendación de arquitectura avanzada para escalabilidad y seguridad:
- Para descargas seguras, la API puede generar **URLs Prefirmadas temporales (Pre-Signed URLs)** con expiración controlada mediante `s3_client.generate_presigned_url('get_object', ...)`.
- Para cargas de archivos de gran tamaño, la API debería entregar una Pre-Signed URL de subida (`put_object`), de modo que el cliente envíe el archivo directamente a S3 sin transitar por API Gateway ni Lambda, ahorrando memoria y costos de transferencia en la capa serverless.

---

## 4. Cómo Reproducir

Para probar y verificar los endpoints implementados:

```bash
# 1. Subir una imagen en formato binario JPEG
curl -X POST https://[API_URL]/upload \
  -H "Content-Type: image/jpeg" \
  --data-binary "@ruta/a/tu/imagen.jpg"

# 2. Consultar los metadatos de la imagen cargada
curl -X GET https://[API_URL]/metadata/[IMAGE_ID]

# 3. Validar respuesta de error controlado (400 Bad Request) enviando cuerpo vacío
curl -X POST https://[API_URL]/upload
```

---

## 5. Estructura del Repositorio

```text
.
├── README.md                              # Documentación técnica y pauta de evaluación
├── img/                                   # Evidencias gráficas (pantallazos)
│   ├── image_metadata_api_diagram.png    # Diagrama arquitectónico oficial
│   ├── 01_s3_bucket.png                  # S3 Bucket creado
│   ├── 01b_s3_objects.png                # Objeto almacenado en S3
│   ├── 02_dynamodb_table.png             # Tabla DynamoDB ImageMetadata
│   ├── 02b_dynamodb_items.png            # Items registrados en DynamoDB
│   ├── 03_lambda_upload.png              # Función Lambda upload_image
│   ├── 04_lambda_get.png                 # Función Lambda get_image_metadata
│   ├── 05_api_gateway.png                # Recursos y métodos API Gateway
│   ├── 05b_api_stage.png                 # Stage dev de API Gateway
│   ├── 06_postman_post.png               # Prueba POST en Postman
│   ├── 07_postman_get.png                # Prueba GET en Postman
│   ├── 08_cloudwatch_logs.png            # Logs de CloudWatch
│   └── 09_cloudwatch_metrics.png         # Métricas de CloudWatch
└── src/                                   # Código fuente de las funciones serverless
    ├── upload_image.py                   # Lógica Lambda de subida y registro de metadatos
    └── get_image_metadata.py             # Lógica Lambda de consulta de metadatos
```

---

## 6. Conclusión

La arquitectura serverless implementada para **Image Metadata API** fue evaluada y validada en el entorno AWS Learner Lab:
- **Persistencia y Almacenamiento:** Integración correcta entre Amazon S3 y DynamoDB para desacoplar el almacenamiento binario de los metadatos estructurados.
- **Backend Reactivo:** Funciones AWS Lambda ejecutadas bajo demanda con aislamiento y gestión de errores robusta ante cargas incompletas.
- **Monitoreo:** Verificación mediante CloudWatch Logs y CloudWatch Metrics del tiempo de respuesta y trazabilidad de eventos.
