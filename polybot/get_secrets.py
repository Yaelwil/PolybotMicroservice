import os
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, NoRegionError, ClientError

# region_name = os.environ["REGION"]
region_name = os.environ["REGION"]

def get_secret(secret_name):
    # Create a Secrets Manager client
    client = boto3.client('secretsmanager', region_name=region_name)

    try:
        # Retrieve the secret value
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret = get_secret_value_response['SecretString']
    except NoCredentialsError:
        print("Credentials not available")
        return None
    except PartialCredentialsError:
        print("Incomplete credentials")
        return None
    except NoRegionError:
        print("AWS region not specified")
        return None
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"Secret {secret_name} not found in AWS Secrets Manager")
        else:
            print(f"Error retrieving secret {secret_name}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error retrieving secret {secret_name}: {e}")
        return None

    return secret
