"""Set a hosting origin while preserving all existing Lambda credentials in memory."""
import argparse
import json
import subprocess
import boto3

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--origin',required=True)
    parser.add_argument('--profile',default='hackathon')
    parser.add_argument('--region',default='us-east-2')
    args=parser.parse_args()
    def aws(*parts):
        result=subprocess.run(['aws',*parts,'--profile',args.profile,'--region',args.region,'--output','json'],check=True,capture_output=True,text=True)
        return json.loads(result.stdout)
    exported = subprocess.run(['aws','configure','export-credentials','--profile',args.profile,'--format','process'],capture_output=True,text=True,check=True)
    credentials = json.loads(exported.stdout)
    session = boto3.Session(aws_access_key_id=credentials['AccessKeyId'],aws_secret_access_key=credentials['SecretAccessKey'],aws_session_token=credentials['SessionToken'],region_name=args.region)
    client = session.client('lambda')
    stack = session.client('cloudformation').describe_stacks(StackName='vida')['Stacks'][0]
    bucket = next(o['OutputValue'] for o in stack['Outputs'] if o['OutputKey'] == 'DocsBucketName')
    s3 = session.client('s3')
    cors = s3.get_bucket_cors(Bucket=bucket)['CORSRules']
    for rule in cors:
        if 'PUT' in rule.get('AllowedMethods', []):
            rule['AllowedOrigins'] = list(dict.fromkeys([*rule['AllowedOrigins'], args.origin]))
    s3.put_bucket_cors(Bucket=bucket, CORSConfiguration={'CORSRules': cors})
    for name in ['vida-api','vida-ai']:
        config=client.get_function_configuration(FunctionName=name)
        env=config.get('Environment',{}).get('Variables',{})
        env['FRONTEND_URL']=args.origin
        env['DOCS_BUCKET']=bucket
        env.setdefault('CALLBACK_BASE_URL','https://opx3hs5amf.execute-api.us-east-2.amazonaws.com/prod')
        client.update_function_configuration(FunctionName=name,RevisionId=config['RevisionId'],Environment={'Variables':env})
        print(name+': origin and managed document bucket updated; existing credentials preserved')
if __name__=='__main__':main()
