from datetime import datetime
import os
import boto3

images_bucket = os.environ["BUCKET_NAME"]


class UPLOAS_TO_S3:

    def __init__(self, photo_path):
        self.photo_path = photo_path
        self.s3 = boto3.client('s3')

    def rename_photo_with_timestamp(self, photo_path):
        """
        Rename a photo with a timestamp in the format 'yyyy-mm-dd HH:MM:SS'.
        If multiple photos are saved within the same minute, append a counter
        to the filename.

        Parameters:
            photo_path (str): The path to the photo file locally.

        Returns:
            new_photo_path (str): The new path to the photo file locally.
            new_file_name (str): The new file name locally.
        """

        # Get current date and time
        current_time = datetime.now()

        # Format the datetime as required
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")

        # Get the file extension
        file_name, file_extension = os.path.splitext(photo_path)

        # Check if there's already a photo saved in the same minute
        same_minute_files = [f for f in os.listdir(os.path.dirname(photo_path)) if f.startswith(formatted_time)]

        # Construct the new file name
        if same_minute_files:
            # Append a counter to the file name
            counter = len(same_minute_files) + 1
            new_file_name = f"{formatted_time} p{counter}{file_extension}"
        else:
            new_file_name = f"{formatted_time}{file_extension}"

        # Rename the file
        new_photo_path = os.path.join(os.path.dirname(photo_path), new_file_name.lstrip("/"))
        os.rename(photo_path, new_photo_path)
        return new_photo_path, new_file_name

    def ensure_s3_directory_exists(self, bucket, directory):
        """
        Makes sure that the specified directory exists in S3. If not, it creates the folder.

        Parameters:
            bucket (str): Bucket name.
            directory (str): Directory to check.
        """

        try:
            # Check if the directory exists by listing objects in the directory
            self.s3.head_object(Bucket=bucket, Key=(directory + '/'))
        except self.s3.exceptions.ClientError as e:
            # If the directory doesn't exist, create it
            if e.response['Error']['Code'] == '404':
                self.s3.put_object(Bucket=bucket, Key=(directory + '/'))
            else:
                raise  # Raise the exception if it's not a '404 Not Found' error

    def upload_photo_to_s3(self, photo_path):
        """
        Upload the photo to S3 bucket.

        Parameters:
            photo_path (str): The path to the photo file locally.

        Returns:
            s3_key (str): The new path to the photo file in S3.
        """
        # Specify the directory path in the bucket
        s3_directory_path = 'photos'
        s3_predicted_directory_path = 'predicted_photos'
        s3_other_filters_directory_path = 'filtered_photos'
        s3_json_folder = 'json'

        # Ensure the directory exists in the S3 bucket
        self.ensure_s3_directory_exists(images_bucket, s3_directory_path)
        self.ensure_s3_directory_exists(images_bucket, s3_predicted_directory_path)
        self.ensure_s3_directory_exists(images_bucket, s3_other_filters_directory_path)
        self.ensure_s3_directory_exists(images_bucket, s3_json_folder)

        # Extract filename from the path
        filename = os.path.basename(photo_path)

        # Combine directory path and filename to form the S3 key
        s3_key = s3_directory_path + '/' + filename

        # Upload the photo to S3
        self.s3.upload_file(photo_path, images_bucket, s3_key)

        # Return the S3 key
        return s3_key, filename
