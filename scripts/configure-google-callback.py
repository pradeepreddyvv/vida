"""Pin Google's registered callback without changing Notion or exposing credentials."""
import argparse
import json
import subprocess
from urllib.parse import urlparse
import boto3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--redirect-uri', required=True)
    parser.add_argument('--profile', default='hackathon')
    parser.add_argument('--region', default='us-east-2')
    args = parser.parse_args()
    parsed = urlparse(args.redirect_uri)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.query or parsed.fragment or parsed.username or parsed.password or not parsed.path.endswith('/api/auth/google/callback'):
        parser.error('Use the exact registered HTTPS callback, without a query or fragment.')
    exported = subprocess.run(['aws','configure','export-credentials','--profile',args.profile,'--format','process'],capture_output=True,text=True,check=True)
    creds = json.loads(exported.stdout)
    session = boto3.Session(aws_access_key_id=creds['AccessKeyId'],aws_secret_access_key=creds['SecretAccessKey'],aws_session_token=creds['SessionToken'],region_name=args.region)
    client = session.client('lambda')
    for name in ('vida-api','vida-ai'):
        client.get_waiter('function_updated').wait(FunctionName=name)
        config = client.get_function_configuration(FunctionName=name)
        env = dict(config.get('Environment',{}).get('Variables',{}))
        env['GOOGLE_REDIRECT_URI'] = args.redirect_uri
        client.update_function_configuration(FunctionName=name,RevisionId=config['RevisionId'],Environment={'Variables':env})
        print(name + ': Google callback pinned; other configuration preserved.')


if __name__ == '__main__':
    main()
