import telebot
from loguru import logger
import os
import time
from telebot.types import InputFile
from s3_upload import UPLOAS_TO_S3
from send_SQS import SqsQueue
import random
from responses import load_responses


class Bot:

    def __init__(self, token, telegram_chat_url, domain_certificate_file):
        # create a new instance of the TeleBot class.
        # all communication with Telegram servers are done using self.telegram_bot_client
        self.telegram_bot_client = telebot.TeleBot(token)
        # remove any existing webhooks configured in Telegram servers
        self.telegram_bot_client.remove_webhook()
        time.sleep(0.5)

        # set the webhook URL
        with open(domain_certificate_file, 'rb') as cert:
            self.telegram_bot_client.set_webhook(url=f'{telegram_chat_url}/{token}/', certificate=cert, timeout=60)
        # self.telegram_bot_client.set_webhook(url=f'{telegram_chat_url}/{token}/', timeout=60)
        logger.info(f'Telegram Bot information\n\n{self.telegram_bot_client.get_me()}')
        self.responses = load_responses()

    def send_text(self, chat_id, text):
        self.telegram_bot_client.send_message(chat_id, text)

    def send_text_with_quote(self, chat_id, text, quoted_msg_id):
        self.telegram_bot_client.send_message(chat_id, text, reply_to_message_id=quoted_msg_id)

    def is_current_msg_photo(self, msg):
        return 'photo' in msg

    def download_user_photo(self, msg):
        """
        Downloads the photos that sent to the Bot to `photos` directory (should be existed)
        :return:
        """
        if not self.is_current_msg_photo(msg):
            raise RuntimeError(f'Message content of type \'photo\' expected')

        file_info = self.telegram_bot_client.get_file(msg['photo'][-1]['file_id'])
        data = self.telegram_bot_client.download_file(file_info.file_path)
        folder_name = file_info.file_path.split('/')[0]

        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        with open(file_info.file_path, 'wb') as photo:
            photo.write(data)
        return file_info.file_path

    def send_photo(self, chat_id, img_path):
        if not os.path.exists(img_path):
            raise RuntimeError("Image path doesn't exist")

        self.telegram_bot_client.send_photo(
            chat_id,
            InputFile(img_path)
        )

    def handle_message(self, msg):
        """Bot Main message handler"""

        logger.info(f'Incoming message: {msg}')

        # Check if the user's message contains a greeting
        if 'text' in msg and any(word.lower() in ['hi', 'hello'] for word in msg['text'].split()):
            greeting_response = random.choice(self.responses['greetings'])
            self.send_text(msg['chat']['id'], greeting_response)
        elif 'text' in msg and any(word in msg['text'].lower() for word in ['how are you', 'how you doing']):
            well_being_response = random.choice(self.responses['well_being'])
            self.send_text(msg['chat']['id'], well_being_response)
        elif 'text' in msg and any(word in msg['text'].lower() for word in ['thank']):
            thanks_response = random.choice(self.responses['thanks'])
            self.send_text(msg['chat']['id'], thanks_response)
        elif 'text' in msg and any(word in msg['text'].lower() for word in ['filter', 'which filters']):
            filter_response_intro = random.choice(self.responses['filter']['intro'])
            filter_response_options = "\n".join(self.responses['filter']['options'])
            full_filter_response = f"{filter_response_intro}\n\nAvailable Filters:\n{filter_response_options}"
            self.send_text(msg['chat']['id'], full_filter_response)
        elif 'text' in msg and any(word in msg['text'].lower() for word in ['help']):
            help_response = '\n'.join(self.responses['help'])
            self.send_text(msg['chat']['id'], help_response)
        elif 'text' in msg and 'what is' in msg['text'].lower() and any(word in msg['text'].lower() for word in
                                                                        ['blur', 'contour', 'rotate', 'salt and pepper',
                                                                         'segment', 'random colors', 'predict']):
            # Extract the filter mentioned in the message
            mentioned_filter = next((word for word in
                                     ['blur', 'contour', 'rotate', 'salt and pepper', 'segment', 'random colors',
                                      'predict'] if word in msg['text'].lower()), None)
            if mentioned_filter:
                # Provide relevant information based on the mentioned filter
                if mentioned_filter == 'blur':
                    self.send_text(msg['chat']['id'], self.responses['blur_info'])
                elif mentioned_filter == 'contour':
                    self.send_text(msg['chat']['id'], self.responses['contour_info'])
                elif mentioned_filter == 'rotate':
                    self.send_text(msg['chat']['id'], self.responses['rotate_info'])
                elif mentioned_filter == 'salt_and_pepper':
                    self.send_text(msg['chat']['id'], self.responses['salt and pepper_info'])
                elif mentioned_filter == 'segment':
                    self.send_text(msg['chat']['id'], self.responses['segment_info'])
                elif mentioned_filter == 'random colors':
                    self.send_text(msg['chat']['id'], self.responses['random_colors_info'])
                elif mentioned_filter == 'predict':
                    self.send_text(msg['chat']['id'], self.responses['predict_info'])

        elif 'text' in msg and any(word in msg['text'].lower() for word in ['blur', 'contour', 'rotate', 'salt and pepper', 'segment', 'random color', 'predict']):
            self.send_text(msg['chat']['id'], "Don't forget to send photo")
        else:
            # If no greeting or well-being question, respond with the original message
            default_response = random.choice(self.responses['default'])
            self.send_text(msg['chat']['id'], default_response)

class ObjectDetectionBot(Bot):

    def __init__(self, token, telegram_chat_url, domain_certificate_file):
        super().__init__(token, telegram_chat_url, domain_certificate_file)
        self.responses = load_responses()

    def handle_message(self, msg):
        logger.info(f'Incoming message: {msg}')
        if self.is_current_msg_photo(msg):
            photo_path = self.download_user_photo(msg)
            if 'caption' in msg:
                photo_caption = msg['caption'].lower()
                if ('blur' in photo_caption or
                        'contour' in photo_caption or
                        'rotate' in photo_caption or
                        'salt and pepper' in photo_caption or
                        'segment' in photo_caption or
                        'random color' in photo_caption or
                        'predict' in photo_caption):
                    chat_id = msg['chat']['id']
                    s3_key, file_name = self.upload_to_s3(photo_path)
                    self.send_sqs_queue(chat_id, photo_caption, s3_key, file_name)
                    if self.send_sqs_queue:
                        self.send_text(msg['chat']['id'], "Your image is being processed. Please wait...")
                    else:
                        self.send_text(msg['chat']['id'], "there was an error, please try again")
                else:
                    # If no specific filter is mentioned, respond with a default message
                    default_response = random.choice(self.responses['default'])
                    self.send_text(msg['chat']['id'], default_response)

            else:
                # If photo is sent without a caption, return a random response from the JSON file
                no_captions_response = random.choice(self.responses['photo_errors']['no_caption'])
                self.send_text(msg['chat']['id'], no_captions_response)

        # If the message doesn't contain a photo with a caption, handle it as a regular text message
        else:
            super().handle_message(msg)

    def upload_to_s3(self, photo_path):
        try:
            s3_uploader = UPLOAS_TO_S3(photo_path)
            new_photo_path, new_file_name = s3_uploader.rename_photo_with_timestamp(photo_path)
            s3_key, filename = s3_uploader.upload_photo_to_s3(new_photo_path)
            if s3_key:
                logger.info(f"Successfully uploaded photo to S3 with key: {s3_key}")
                return s3_key, filename
            else:
                logger.error("Failed to upload photo to S3.")
        except Exception as e:
            logger.error(f"Error uploading photo to S3: {e}")

    def send_sqs_queue(self, chat_id, photo_caption, s3_key, file_name):
        try:
            sqs_sender = SqsQueue()
            sqs_sender.send_sqs_queue(chat_id, photo_caption, s3_key, file_name)
        except Exception as e:
            logger.error(f"Error sending message to SQS queue: {e}")
