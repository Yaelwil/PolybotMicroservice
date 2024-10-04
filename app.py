import os
from loguru import logger
import flask
from flask import request, jsonify
import boto3
from bot import ObjectDetectionBot
from get_secrets import get_secret
import results
from get_cert import get_cert

app = flask.Flask(__name__)
REGION = os.environ["REGION"]
TELEGRAM_APP_URL = os.environ["TELEGRAM_APP_URL"]
DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
BUCKET_NAME = os.environ["BUCKET_NAME"]
alb_url = os.environ["ALB_URL"]
cert_prefix = os.environ["CERT_PREFIX"]
TELEGRAM_TOKEN_PREFIX = os.environ["TELEGRAM_TOKEN_PREFIX"]

print(f"TELEGRAM_APP_URL: {TELEGRAM_APP_URL}")

TELEGRAM_TOKEN = get_secret(TELEGRAM_TOKEN_PREFIX)

if TELEGRAM_TOKEN:
    logger.info('Retrieved TELEGRAM_TOKEN from Secrets Manager')
else:
    raise ValueError("Failed to retrieve secret TELEGRAM_TOKEN from Secrets Manager")

DOMAIN_CERTIFICATE = get_cert(cert_prefix)

if DOMAIN_CERTIFICATE:
    logger.info('Retrieved DOMAIN_CERTIFICATE from Secrets Manager')
else:
    raise ValueError("Failed to retrieve secret DOMAIN_CERTIFICATE from Secrets Manager")

domain_certificate_file = 'DOMAIN_CERTIFICATE.pem'

with open(domain_certificate_file, 'w') as file:
    file.write(DOMAIN_CERTIFICATE)

logger.info('Created certificate file successfully')

# Initialize bot outside of __main__ block
bot = ObjectDetectionBot(TELEGRAM_TOKEN, TELEGRAM_APP_URL, domain_certificate_file)


@app.route('/', methods=['GET'])
def index():
    return 'Ok'


@app.route(f'/{TELEGRAM_TOKEN}/', methods=['POST'])
def webhook():
    req = request.get_json()
    bot.handle_message(req['message'])
    return 'Ok'


@app.route('/results_predict', methods=['POST'])
def results_predict():
    prediction_id = request.args.get('predictionId')
    if not prediction_id:
        return jsonify({'error': 'Missing predictionId'}), 400

    # Fetch prediction results
    response_json, status_code = results.fetch_results_predict(prediction_id)

    # Check if the fetch was successful
    if status_code != 200:
        return jsonify(response_json), status_code

    chat_id = response_json.get('chat_id')
    text_results = response_json.get('text_results')

    if not chat_id:
        return jsonify({'error': 'chat_id not found in the response'}), 400

    # Send the message to the user via Telegram

    bot.send_text(chat_id, text_results)
    logger.info("Successfully sent results to the end user")
    return jsonify({'status': 'Message sent successfully'}), 200


@app.route('/results_filter', methods=['POST'])
def results_filter():
    s3 = boto3.client('s3')
    try:
        data = request.json
        full_s3_path = data.get('full_s3_path')
        processed_img_path = data.get('processed_img_path')
        chat_id = data.get('chat_id')

        if not full_s3_path or not processed_img_path:
            return jsonify({'error': 'Missing full_s3_path or img_name'}), 400

        logger.info("Received request")
        logger.debug(f'full_s3_path: {full_s3_path}')
        logger.debug(f'img_name: {processed_img_path}')
        logger.debug(f'chat_id: {chat_id}')

        s3.download_file(BUCKET_NAME, full_s3_path, processed_img_path)

        logger.debug(f'img_name: {processed_img_path}')

        # Send the filtered photo to the end-user via Telegram
        try:
            bot.send_photo(chat_id, img_path=processed_img_path)
            logger.info('Successfully sent filtered photo to Telegram')

        except Exception as e:
            logger.error(f'Error sending photo to Telegram: {str(e)}')
            return jsonify({'error': f'Error sending photo to Telegram: {str(e)}'}), 500

        return jsonify({'status': 'Ok'}), 200

    except Exception as e:
        logger.error(f'Internal Server Error: {str(e)}')
        return jsonify({'error': f'Internal Server Error: {str(e)}'}), 500


@app.route('/loadTest/', methods=['POST'])
def load_test():
    req = request.get_json()
    bot.handle_message(req['message'])
    return 'Ok'


@app.route('/health_checks/', methods=['GET'])
def health_checks():
    return 'Ok', 200


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8443)