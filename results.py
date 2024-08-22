import json
import boto3
from botocore.exceptions import ClientError
from flask import jsonify, request
from loguru import logger
import os

REGION = os.environ["REGION"]
DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
BUCKET_NAME = os.environ["BUCKET_NAME"]
alb_url = os.environ["ALB_URL"]

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table = dynamodb.Table(DYNAMODB_TABLE_NAME)
s3 = boto3.client('s3')


def fetch_results_predict(prediction_id):
    try:
        response = table.get_item(Key={'prediction_id': prediction_id})
        item = response.get('Item')
        if not item:
            return {'error': 'No results found for the given predictionId'}, 404

        chat_id = item.get('chat_id')
        if not chat_id:
            return {'error': 'chat_id not found in the item'}, 404

        text_results = item.get('results')  # Replace 'results' with your actual attribute name
        if not text_results:
            return {'error': 'No results found in the item'}, 404

        return {'status': 'Ok', 'prediction_id': prediction_id, 'chat_id': chat_id, 'text_results': text_results}, 200

    except ClientError as e:
        logger.error(f'Error retrieving results from DynamoDB: {str(e)}')
        return {'error': 'Error retrieving results from DynamoDB'}, 500

    except Exception as e:
        logger.error(f'Error retrieving results: {str(e)}')
        return {'error': f'Error retrieving results: {str(e)}'}, 500


def results_filters(images_bucket, full_s3_path, img_name):
    try:
        # Download the image from S3
        s3.download_file(images_bucket, full_s3_path, img_name)
        logger.info(f'Successfully downloaded photo from S3: {img_name}')

        return img_name

    except Exception as e:
        logger.error(f'Error processing photo: {str(e)}')
        raise  # Propagate the error to be handled in the Flask route
