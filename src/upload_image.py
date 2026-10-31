import base64
import json
import os
import re
from uuid import uuid4

import boto3

# Variables de entorno
BUCKET_NAME = os.getenv('BUCKET_NAME')
TABLE_NAME = os.getenv('TABLE_NAME')

# Clientes AWS
s3_client = boto3.client('s3')
dynamodb_resource = boto3.resource('dynamodb')
table = dynamodb_resource.Table(TABLE_NAME)

def get_image_bytes(event):
    body = event.get('body')
    if not body:
        raise ValueError("No image data received")
    if event.get('isBase64Encoded'):
        return base64.b64decode(body)
    return body.encode('utf-8') if isinstance(body, str) else body

def upload_image(event, context):
    try:
        # Decodificar body y obtener los bytes reales de la imagen
        image_bytes = get_image_bytes(event)
        
        # Generar un nombre único para la imagen sin caracteres especiales
        image_id = re.sub(r'[^a-zA-Z0-9]', '', str(uuid4()))
        image_name = f"{image_id}.jpg"

        # Subir la imagen al bucket S3 con su ContentType adecuado
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=image_name,
            Body=image_bytes,
            ContentType='image/jpeg'
        )

        # Generar URL prefirmada de descarga (vigencia de 1 hora = 3600 segundos)
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': image_name},
            ExpiresIn=3600
        )

        # URL base informativa
        url_s3 = f"https://{BUCKET_NAME}.s3.amazonaws.com/{image_name}"

        # Guardar metadatos en DynamoDB incluyendo key y url_s3
        table.put_item(Item={
            'image_id': image_id,
            'key': image_name,
            'url_s3': url_s3,
            'size': len(image_bytes)
        })

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Image uploaded successfully!',
                'image_id': image_id,
                'url': presigned_url
            })
        }

    except ValueError as e:
        print(f"Error de validacion: {str(e)}")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': str(e)})
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
