"""Prompt locally for existing Notion OAuth credentials; preserve other Lambda settings."""
import argparse
import getpass
import json
import subprocess
import boto3

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--profile',default='hackathon')
    parser.add_argument('--region',default='us-east-2')
    args=parser.parse_args()
    client_id=getpass.getpass('Existing Notion OAuth client ID (hidden): ').strip()
    secret=getpass.getpass('Existing Notion OAuth client secret (hidden): ').strip()
    if not client_id or not secret:
        raise ValueError('Both OAuth fields are required; an internal API token is not an OAuth client secret.')
    exported=subprocess.run(['aws','configure','export-credentials','--profile',args.profile,'--format','process'],check=True,capture_output=True,text=True)
    credentials=json.loads(exported.stdout)
    session=boto3.Session(aws_access_key_id=credentials['AccessKeyId'],aws_secret_access_key=credentials['SecretAccessKey'],aws_session_token=credentials['SessionToken'],region_name=args.region)
    client=session.client('lambda')
    for name in ['vida-api','vida-ai']:
        config=client.get_function_configuration(FunctionName=name)
        env=config.get('Environment',{}).get('Variables',{})
        env.update(NOTION_CLIENT_ID=client_id,NOTION_CLIENT_SECRET=secret)
        client.update_function_configuration(FunctionName=name,RevisionId=config['RevisionId'],Environment={'Variables':env})
        print(name+': Notion configuration saved; values were not logged.')
    print('Wait for Lambda updates to finish, then select Connect in Vida Settings.')
if __name__=='__main__': main()
