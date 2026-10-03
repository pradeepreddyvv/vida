"""Load provider credentials from Secrets Manager without logging their values."""
import json
import os
import boto3

_loaded = False

def load_credentials():
    global _loaded
    if _loaded:
        return
    arn = os.environ.get('OAUTH_SECRET_ARN')
    if arn:
        client = boto3.client('secretsmanager', region_name=os.environ.get('REGION', 'us-east-2'))
        data = json.loads(client.get_secret_value(SecretId=arn)['SecretString'])
        for key in ('GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'NOTION_CLIENT_ID', 'NOTION_CLIENT_SECRET'):
            if data.get(key):
                os.environ[key] = str(data[key])
    _loaded = True
