"""Wire the approved workflow stack to Vida without logging existing secrets."""
import json
import subprocess
import boto3

def main():
    creds=json.loads(subprocess.run(['aws','configure','export-credentials','--profile','hackathon','--format','process'],capture_output=True,text=True,check=True).stdout)
    session=boto3.Session(aws_access_key_id=creds['AccessKeyId'],aws_secret_access_key=creds['SecretAccessKey'],aws_session_token=creds['SessionToken'],region_name='us-east-2')
    stack=session.client('cloudformation').describe_stacks(StackName='vida-workflows')['Stacks'][0]
    if stack['StackStatus'] not in ('CREATE_COMPLETE','UPDATE_COMPLETE'): raise ValueError('Workflow stack is not ready')
    arn=next(x['OutputValue'] for x in stack['Outputs'] if x['OutputKey']=='WorkflowArn')
    client=session.client('lambda'); cfg=client.get_function_configuration(FunctionName='vida-api')
    env=cfg.get('Environment',{}).get('Variables',{})
    env['WORKFLOW_ARN']=arn
    client.update_function_configuration(FunctionName='vida-api',RevisionId=cfg['RevisionId'],Environment={'Variables':env})
    print('Workflow configured; existing secrets preserved and not logged.')

if __name__=='__main__': main()
