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
2. Procesar y almacenar metadatos (identificador único `image_id`, nombre de archivo `key`, URL informativa `url_s3` y tamaño en bytes `size`) en una base de datos NoSQL administrada (**Amazon DynamoDB**).
3. Recuperar dichos metadatos y un enlace seguro de descarga mediante peticiones HTTP RESTful a través de **Amazon API Gateway**.
4. Ejecutar la lógica de backend sin administración de servidores mediante funciones **AWS Lambda** desarrolladas en Python 3.12.
5. Monitorear la infraestructura, analizar logs y auditar métricas mediante **Amazon CloudWatch**.

### Diagrama de Arquitectura
![metadata api diagram](img/image_metadata_api_diagram.png)

### Flujo de la Solución
1. El cliente envía una petición HTTP `POST /upload` con el archivo de imagen a través de **API Gateway**.
2. API Gateway invoca mediante integración tipo Proxy a la función Lambda `upload_image`.
3. La función decodifica el cuerpo (soportando Base64), genera un identificador alfanumérico único (`image_id`), almacena el objeto binario en el bucket **S3** con `ContentType='image/jpeg'`, genera una **URL prefirmada de descarga (vigencia de 1 hora)** y persiste los metadatos (`image_id`, `key`, `url_s3`, `size`) en la tabla **DynamoDB** (`ImageMetadata`).
4. Para consultar la información de la imagen, el cliente envía una petición `GET /metadata/{image_id}` a API Gateway.
5. API Gateway invoca a la función Lambda `get_image_metadata`, la cual extrae el parámetro de ruta de forma segura, consulta la tabla **DynamoDB** por clave primaria, genera en tiempo de ejecución una nueva **URL prefirmada de descarga válida por 1 hora** y retorna el objeto serializado en JSON con código `200 OK` (o `404 Not Found` si el identificador no existe).

---

## 2. Paso a Paso de Implementación

### Paso 1: Creación del Bucket Amazon S3 (IE2.2.1)
- **Servicio:** Amazon Simple Storage Service (S3)
- **Nombre del Bucket:** `my-image-storage-bucket-[ACCOUNT_ID]`
- **Región:** `us-east-1`
- **Configuración de Seguridad y Almacenamiento Verificada:**
  - Cifrado en reposo: SSE-S3 (habilitado por defecto en Amazon S3).
  - Bloqueo de acceso público (Block Public Access): Activo (`BlockPublicAcls: true`, `IgnorePublicAcls: true`, `BlockPublicPolicy: true`, `RestrictPublicBuckets: true`), garantizando que los objetos no queden expuestos anónimamente a internet.
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
*Figura 2.1: Metadatos registrados en DynamoDB (`image_id`, `key`, `url_s3`, `size`).*

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
- **Lógica implementada:** Decodificación de body binario/Base64, subida a S3 con `ContentType='image/jpeg'`, generación de URL prefirmada de 1 hora, inserción de metadatos en DynamoDB y manejo de error `400 Bad Request` ante carga vacía.

![Lambda upload_image](img/03_lambda_upload.png)
*Figura 3: Configuración y variables de entorno de la función `upload_image`.*

#### 3.2 Función `get_image_metadata`
- **Runtime:** Python 3.12
- **Handler:** `get_image_metadata.get_image_metadata`
- **Timeout:** 30 segundos
- **Rol IAM:** `LabRole`
- **Variables de Entorno:**
  - `TABLE_NAME`: `ImageMetadata`
  - `BUCKET_NAME`: `my-image-storage-bucket-[ACCOUNT_ID]`
- **Lógica implementada:** Extracción resiliente de `pathParameters` (manejando `None`), consulta por `image_id`, generación dinámica de URL prefirmada de descarga, retorno `404 Not Found` en caso de no existir y serialización JSON adecuada para campos `Decimal`.

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
  "image_id": "[IMAGE_ID]",
  "url": "https://my-image-storage-bucket-[ACCOUNT_ID].s3.amazonaws.com/[IMAGE_ID].jpg?AWSAccessKeyId=...&Signature=...&Expires=..."
}
```

![Prueba POST Postman](img/06_postman_post.png)
*Figura 6: Solicitud POST /upload exitosa.*

#### 5.2 Consulta de Metadatos (`GET /metadata/{image_id}`)
- **Método:** `GET`
- **Endpoint:** `https://[API_ID].execute-api.us-east-1.amazonaws.com/dev/metadata/[IMAGE_ID]`
- **Respuesta:** `200 OK`
```json
{
  "image_id": "[IMAGE_ID]",
  "size": 524.0,
  "url": "https://my-image-storage-bucket-[ACCOUNT_ID].s3.amazonaws.com/[IMAGE_ID].jpg?AWSAccessKeyId=...&Signature=...&Expires=...",
  "key": "[IMAGE_ID].jpg",
  "url_s3": "https://my-image-storage-bucket-[ACCOUNT_ID].s3.amazonaws.com/[IMAGE_ID].jpg"
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
[PENDIENTE: pegar REPORT del cold start de get_image_metadata]
```

![CloudWatch Logs](img/08_cloudwatch_logs.png)
*Figura 8: Grupos de registro y eventos en CloudWatch Logs.*

#### 6.2 Métricas de Rendimiento en CloudWatch
Métricas reales recopiladas en CloudWatch tras el ciclo de pruebas:

| Métrica | `upload_image` | `get_image_metadata` |
|---|---|---|
| Invocaciones (Invocations) | 3 | 3 |
| Errores de ejecución Lambda (Errors) | 0 * | 0 * |
| Duración (Duration) | 505.51 ms | [PENDIENTE: evidencia real] |
| Tiempo de Inicialización (Init Duration) | 528.08 ms | [PENDIENTE: evidencia real] |
| Duración en Invocación Caliente (Warm) | [PENDIENTE: pegar REPORT de una invocación en caliente de cada función] | [PENDIENTE: pegar REPORT de una invocación en caliente de cada función] |
| Memoria Máxima Utilizada (Max Memory) | 96 MB / 128 MB | 90 MB / 128 MB |

*\* Nota sobre la métrica Errors:* Las excepciones no controladas se capturan en el bloque `try/except` de cada función Lambda devolviendo un código HTTP 500 o 400 controlado en la respuesta JSON. Debido a esto, el contador de métricas nativo `Errors` de AWS Lambda (que solo contabiliza caídas no controladas del runtime) registra 0.

![CloudWatch Métricas](img/09_cloudwatch_metrics.png)
*Figura 9: Métricas agregadas de invocaciones y duración en CloudWatch.*

#### 6.3 Error Provocado y Análisis
Como parte de las pruebas de resiliencia y troubleshooting:
- **Prueba 1 (Cuerpo vacío en subida):** En Postman [PENDIENTE: confirmar herramienta usada] se envió una petición `POST /upload` sin cuerpo (body vacío). La función capturó la excepción `ValueError`, registrando en CloudWatch `Error de validacion: No image data received` y devolviendo al cliente un código HTTP `400 Bad Request` con `{"error": "No image data received"}` en lugar de un error 500 no controlado.
- **Prueba 2 (Identificador inexistente):** Se consultó `GET /metadata/nonexistent99999`. La función verificó la ausencia del ítem en DynamoDB y retornó de forma limpia un código `404 Not Found` con `{"message": "Image not found"}`.

---

## 3. Estrategias de Optimización y Aseguramiento de Escalabilidad (IL2.3)

### 3.1 Mejoras de Rendimiento Aplicadas
1. **Reutilización de Clientes SDK fuera del Handler:**
   Los clientes `boto3.client('s3')` y `boto3.resource('dynamodb')` se inicializan fuera de las funciones `upload_image` y `get_image_metadata`. La diferencia observada entre una primera invocación (cold start) y una ejecución caliente se debe principalmente a la inicialización del entorno y runtime (Init Duration). La reutilización de los clientes SDK fuera del handler ayuda a las invocaciones subsiguientes al evitar la sobrecarga de renegociar conexiones TCP y sesiones TLS hacia los servicios de AWS.
2. **Impacto de la Memoria en Cómputo y CPU:**
   En AWS Lambda, la vCPU asignada es proporcional a la memoria RAM configurada. Las funciones están configuradas actualmente con **128 MB**. Pasar a **512 MB** aumentaría la CPU asignada de forma proporcional a la memoria (aprox. 4 veces respecto a 128 MB), lo que aceleraría el procesamiento criptográfico de firmas de URLs prefirmadas y la transferencia a S3, reduciendo la duración facturada.
3. **Mitigación de Arranques en Frío (Cold Starts):**
   Para entornos de producción con requerimientos de latencia estricta, la habilitación de **Provisioned Concurrency** (Concurrencia Aprovisionada) mantiene entornos de ejecución preinicializados, eliminando la sobrecarga del Init Duration en picos de demanda.
4. **Modo On-Demand en DynamoDB:**
   La tabla opera en modo `PAY_PER_REQUEST`, lo que evita caídas por saturación de lectura o escritura (*throttling*) y elimina costos por capacidad aprovisionada no utilizada.

### 3.2 Acceso Seguro Mediante S3 Pre-Signed URLs (Implementado)
Dado que el bucket mantiene activo el bloqueo de acceso público (*Block Public Access*) por buenas prácticas de seguridad en la nube, los objetos no son accesibles mediante URLs públicas tradicionales.
Para resolver esto de forma segura y eficiente:
- La función `upload_image` genera y retorna una **URL Prefirmada (Pre-Signed URL)** con una vigencia de 1 hora (`ExpiresIn=3600`), permitiendo al usuario descargar o visualizar la imagen de forma temporal y autenticada.
- Al consultar `GET /metadata/{image_id}`, la función `get_image_metadata` genera dinámicamente una nueva URL prefirmada con vigencia de 1 hora a partir de la `key` almacenada, garantizando que el cliente siempre reciba un enlace funcional sin comprometer la seguridad del bucket.
- **Recomendación para cargas masivas:** Como siguiente paso evolutivo en arquitectura serverless, para archivos de gran tamaño se recomienda que API Gateway devuelva una URL prefirmada de subida (`put_object`), permitiendo que el cliente envíe el archivo directamente a S3 sin transitar por API Gateway ni Lambda.

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
- **Persistencia y Almacenamiento:** Integración correcta entre Amazon S3 y DynamoDB para desacoplar el almacenamiento binario de los metadatos estructurados, con entrega de URLs prefirmadas de 1 hora respetando el bloqueo de acceso público del bucket.
- **Backend Reactivo:** Funciones AWS Lambda ejecutadas bajo demanda con aislamiento y gestión de errores robusta ante cargas incompletas.
- **Monitoreo:** Verificación mediante CloudWatch Logs y Metrics de la duración y errores de las funciones Lambda.
