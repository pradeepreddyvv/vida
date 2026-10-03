"""Prompt locally for a Tavily search key; preserve other Lambda settings."""
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
    secret=getpass.getpass('Tavily API key (hidden): ').strip()
    if not secret:
        raise ValueError('A Tavily API key is required.')
    exported=subprocess.run(['aws','configure','export-credentials','--profile',args.profile,'--format','process'],check=True,capture_output=True,text=True)
    credentials=json.loads(exported.stdout)
    session=boto3.Session(aws_access_key_id=credentials['AccessKeyId'],aws_secret_access_key=credentials['SecretAccessKey'],aws_session_token=credentials['SessionToken'],region_name=args.region)
    client=session.client('lambda')
    for name in ['vida-api','vida-ai']:
        config=client.get_function_configuration(FunctionName=name)
        env=config.get('Environment',{}).get('Variables',{})
        env.update(TAVILY_API_KEY=secret)
        client.update_function_configuration(FunctionName=name,RevisionId=config['RevisionId'],Environment={'Variables':env})
        print(name+': Web search key saved; values were not logged.')
    print('Wait for Lambda updates to finish, then ask Vida to research a public topic.')
if __name__=='__main__': main()
