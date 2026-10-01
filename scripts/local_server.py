"""
Local development server for Vida.
Wraps the Lambda handler code with a Flask server.
Uses DynamoDB Local (Java) or falls back to in-memory storage.
"""
import json
import os
import sys
import subprocess
import time
import signal
import threading

_functions_dir = os.path.join(os.path.dirname(__file__), '..', 'backend', 'functions')
sys.path.insert(0, _functions_dir)
sys.path.insert(0, os.path.join(_functions_dir, 'api'))

os.environ.setdefault('TABLE_NAME', 'vida-main')
os.environ.setdefault('REGION', 'us-east-1')
os.environ.setdefault('BEDROCK_MODEL_ID', 'amazon.nova-lite-v1:0')
os.environ.setdefault('DOCS_BUCKET', 'vida-docs-local')
os.environ.setdefault('AI_FUNCTION_NAME', 'vida-ai-local')
os.environ.setdefault('AWS_PROFILE', 'hackathon')

from flask import Flask, request, jsonify
import boto3

app = Flask(__name__)

DYNAMO_LOCAL_PORT = 8000
dynamo_process = None
LOCAL_DOCS_DIR = os.path.join(os.path.dirname(__file__), '..', 'local', 'docs')


def start_dynamodb_local():
    global dynamo_process
    dynamo_jar_dir = os.path.join(os.path.dirname(__file__), '..', 'local', 'dynamodb')

    if not os.path.exists(os.path.join(dynamo_jar_dir, 'DynamoDBLocal.jar')):
        print("Downloading DynamoDB Local...")
        os.makedirs(dynamo_jar_dir, exist_ok=True)
        subprocess.run([
            'curl', '-sL',
            'https://d1ni2b6xgvw0s0.cloudfront.net/v2.x/dynamodb_local_latest.tar.gz',
            '-o', os.path.join(dynamo_jar_dir, 'dynamodb_local.tar.gz')
        ], check=True)
        subprocess.run([
            'tar', 'xzf', os.path.join(dynamo_jar_dir, 'dynamodb_local.tar.gz'),
            '-C', dynamo_jar_dir
        ], check=True)

    print(f"Starting DynamoDB Local on port {DYNAMO_LOCAL_PORT}...")
    dynamo_process = subprocess.Popen(
        ['java', '-Djava.library.path=./DynamoDBLocal_lib', '-jar', 'DynamoDBLocal.jar',
         '-port', str(DYNAMO_LOCAL_PORT), '-inMemory'],
        cwd=dynamo_jar_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)

    client = boto3.client('dynamodb', endpoint_url=f'http://localhost:{DYNAMO_LOCAL_PORT}',
                          region_name='us-east-1', aws_access_key_id='local', aws_secret_access_key='local')

    try:
        client.describe_table(TableName='vida-main')
        print("Table already exists")
    except client.exceptions.ResourceNotFoundException:
        print("Creating vida-main table...")
        client.create_table(
            TableName='vida-main',
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI2PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI2SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI3PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI3SK', 'AttributeType': 'S'},
            ],
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'},
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'GSI1',
                    'KeySchema': [
                        {'AttributeName': 'GSI1PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI1SK', 'KeyType': 'RANGE'},
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                },
                {
                    'IndexName': 'GSI2',
                    'KeySchema': [
                        {'AttributeName': 'GSI2PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI2SK', 'KeyType': 'RANGE'},
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                },
                {
                    'IndexName': 'GSI3',
                    'KeySchema': [
                        {'AttributeName': 'GSI3PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI3SK', 'KeyType': 'RANGE'},
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                },
            ],
            BillingMode='PAY_PER_REQUEST',
        )
        print("Table created")


def patch_dynamo_for_local():
    """Monkey-patch shared.db to use DynamoDB Local endpoint."""
    import shared.db as db
    original_get_table = db._get_table

    def local_get_table():
        if db._table is None:
            dynamodb = boto3.resource(
                'dynamodb',
                endpoint_url=f'http://localhost:{DYNAMO_LOCAL_PORT}',
                region_name='us-east-1',
                aws_access_key_id='local',
                aws_secret_access_key='local',
            )
            db._table = dynamodb.Table('vida-main')
        return db._table

    db._get_table = local_get_table


def patch_s3_for_local():
    """Redirect S3 operations to local filesystem."""
    os.makedirs(LOCAL_DOCS_DIR, exist_ok=True)

    import shared.utils as utils
    original_response = utils.response

    import boto3 as b3
    original_client = b3.client

    class LocalS3:
        def generate_presigned_url(self, method, Params=None, ExpiresIn=300):
            key = Params.get('Key', 'unknown')
            return f'http://localhost:5001/local-upload/{key}'

        def get_object(self, Bucket=None, Key=None):
            filepath = os.path.join(LOCAL_DOCS_DIR, Key.replace('/', '_'))
            if os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    content = f.read()
                return {'Body': type('Body', (), {'read': lambda self: content})()}
            raise Exception(f"File not found: {Key}")

        def put_object(self, Bucket=None, Key=None, Body=None, **kwargs):
            filepath = os.path.join(LOCAL_DOCS_DIR, Key.replace('/', '_'))
            os.makedirs(os.path.dirname(filepath) if '/' in filepath else LOCAL_DOCS_DIR, exist_ok=True)
            if isinstance(Body, bytes):
                with open(filepath, 'wb') as f:
                    f.write(Body)
            elif isinstance(Body, str):
                with open(filepath, 'w') as f:
                    f.write(Body)

    _local_s3 = LocalS3()

    def patched_client(service, **kwargs):
        if service == 's3':
            return _local_s3
        return original_client(service, **kwargs)

    b3.client = patched_client


def make_event(method, path, body=None, headers=None, query_params=None):
    event = {
        'requestContext': {'http': {'method': method, 'path': path}},
        'rawPath': path,
        'headers': headers or {},
        'queryStringParameters': query_params or {},
    }
    if body is not None:
        event['body'] = json.dumps(body) if isinstance(body, dict) else body
    return event


@app.route('/local-upload/<path:key>', methods=['PUT'])
def local_upload(key):
    filepath = os.path.join(LOCAL_DOCS_DIR, key.replace('/', '_'))
    with open(filepath, 'wb') as f:
        f.write(request.data)
    return jsonify({'status': 'uploaded'}), 200


@app.route('/api/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def proxy_to_handler(subpath):
    from api.handler import handler as api_handler

    method = request.method
    path = f'/api/{subpath}'

    if method == 'OPTIONS':
        resp = jsonify({})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,X-User-Id'
        resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
        return resp

    body = request.get_json(silent=True)
    headers = dict(request.headers)

    event = make_event(method, path, body, headers, dict(request.args))
    result = api_handler(event, None)

    status = result.get('statusCode', 200)
    resp_body = result.get('body', '{}')
    resp_headers = result.get('headers', {})

    response = app.response_class(
        response=resp_body,
        status=status,
        mimetype='application/json',
    )
    for k, v in resp_headers.items():
        response.headers[k] = v
    return response


def run_ai_job_inline(event):
    """Run AI job synchronously in a background thread (local only)."""
    from ai.handler import handler as ai_handler
    ai_handler(event, None)


@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,X-User-Id'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    return response


def patch_lambda_invoke():
    """Replace Lambda invoke with local execution."""
    import boto3 as b3
    original_client = b3.client

    class LocalLambdaClient:
        def invoke(self, FunctionName=None, InvocationType=None, Payload=None):
            payload = json.loads(Payload) if isinstance(Payload, str) else Payload
            print(f"[LOCAL] AI job: {payload.get('job_type')} for user {payload.get('user_id')}")
            thread = threading.Thread(target=run_ai_job_inline, args=(payload,))
            thread.start()
            return {'StatusCode': 202}

    _local_lambda = LocalLambdaClient()
    _original_boto_client = b3.client

    def patched_client(service, **kwargs):
        if service == 'lambda':
            return _local_lambda
        if service == 's3':
            from types import SimpleNamespace
            return _patched_s3
        return _original_boto_client(service, **kwargs)

    # We need a more targeted patch — only for lambda
    import api.handler as api_mod
    original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

    # Simpler: just patch at the module level
    class PatchedBoto3:
        @staticmethod
        def client(service, **kwargs):
            if service == 'lambda':
                return _local_lambda
            if service == 's3':
                return _patched_s3
            return original_client(service, **kwargs)

        @staticmethod
        def resource(service, **kwargs):
            return b3.resource(service, **kwargs)

    # We'll store the local S3 reference
    global _patched_s3
    _patched_s3 = type('LocalS3', (), {
        'generate_presigned_url': lambda self, method, Params=None, ExpiresIn=300: f'http://localhost:5001/local-upload/{Params.get("Key", "unknown")}',
        'get_object': lambda self, Bucket=None, Key=None: _s3_get(Key),
        'put_object': lambda self, Bucket=None, Key=None, Body=None, **kw: _s3_put(Key, Body),
    })()


def _s3_get(key):
    filepath = os.path.join(LOCAL_DOCS_DIR, key.replace('/', '_'))
    if os.path.exists(filepath):
        with open(filepath, 'rb') as f:
            content = f.read()
        return {'Body': type('Body', (), {'read': lambda self: content})()}
    raise Exception(f"File not found: {key}")


def _s3_put(key, body):
    filepath = os.path.join(LOCAL_DOCS_DIR, key.replace('/', '_'))
    with open(filepath, 'wb') as f:
        if isinstance(body, bytes):
            f.write(body)
        elif isinstance(body, str):
            f.write(body.encode())


def cleanup(signum, frame):
    global dynamo_process
    if dynamo_process:
        print("\nStopping DynamoDB Local...")
        dynamo_process.terminate()
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print("=== Vida Local Development Server ===")

    start_dynamodb_local()
    patch_dynamo_for_local()
    patch_s3_for_local()

    # Patch boto3.client for lambda invoke to run locally
    import boto3 as b3
    _orig_client = b3.client

    class _LocalLambda:
        def invoke(self, FunctionName=None, InvocationType=None, Payload=None):
            payload = json.loads(Payload) if isinstance(Payload, str) else Payload
            print(f"  [AI JOB] {payload.get('job_type')} for user {payload.get('user_id')}")
            t = threading.Thread(target=run_ai_job_inline, args=(payload,), daemon=True)
            t.start()
            return {'StatusCode': 202}

    _ll = _LocalLambda()

    def _patched_client(service, **kwargs):
        if service == 'lambda':
            return _ll
        if service == 's3':
            return _patched_s3
        return _orig_client(service, **kwargs)

    _patched_s3 = type('LS3', (), {
        'generate_presigned_url': lambda self, m, Params=None, ExpiresIn=300: f'http://localhost:5001/local-upload/{Params.get("Key", "unknown")}',
        'get_object': lambda self, Bucket=None, Key=None: _s3_get(Key),
        'put_object': lambda self, Bucket=None, Key=None, Body=None, **kw: _s3_put(Key, Body),
    })()

    b3.client = _patched_client

    print(f"DynamoDB Local: http://localhost:{DYNAMO_LOCAL_PORT}")
    print(f"API Server: http://localhost:5001")
    print(f"Frontend: Run 'npm run dev' in frontend/ (proxied to :5001)")
    print()

    app.run(host='0.0.0.0', port=5001, debug=False)
