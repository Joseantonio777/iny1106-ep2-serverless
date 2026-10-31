import json
import os
from decimal import Decimal

import boto3

# Variables de entorno
TABLE_NAME = os.getenv('TABLE_NAME')

# Cliente de DynamoDB
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

        # Convertir y retornar el item (incluye image_id, url y size)
        item = response['Item']
        return {
            'statusCode': 200,
            'body': json.dumps(item, default=decimal_default)
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
