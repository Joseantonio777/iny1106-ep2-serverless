import json
import os
from decimal import Decimal

import boto3

# Variables de entorno
TABLE_NAME = os.getenv('TABLE_NAME')
BUCKET_NAME = os.getenv('BUCKET_NAME')

# Clientes AWS
s3_client = boto3.client('s3')
dynamodb_resource = boto3.resource('dynamodb')
table = dynamodb_resource.Table(TABLE_NAME)

# Función para convertir Decimals a tipos serializables por JSON
def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def get_image_metadata(event, context):
    try:
        # Extraer image_id de forma segura manejando pathParameters ausente o None
        path_params = event.get('pathParameters') or {}
        image_id = path_params.get('image_id')
        print(f"Received image_id: {image_id}")

        if not image_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Image ID is required'})
            }

        # Consultar DynamoDB para obtener los metadatos de la imagen
        response = table.get_item(Key={'image_id': image_id})

        # Verificar si el item fue encontrado en la tabla
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'body': json.dumps({'message': 'Image not found'})
            }

        item = response['Item']
        key = item.get('key') or f"{image_id}.jpg"
        bucket = BUCKET_NAME or (item.get('url_s3', '').split('.s3.amazonaws.com')[0].replace('https://', '') if item.get('url_s3') else None)

        # Generar URL prefirmada de descarga válida por 1 hora (3600 s)
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=3600
        )

        response_body = {
            'image_id': item['image_id'],
            'size': item['size'],
            'url': presigned_url
        }

        if 'key' in item:
            response_body['key'] = item['key']
        if 'url_s3' in item:
            response_body['url_s3'] = item['url_s3']

        return {
            'statusCode': 200,
            'body': json.dumps(response_body, default=decimal_default)
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
