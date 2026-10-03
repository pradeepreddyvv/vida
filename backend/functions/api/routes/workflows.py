"""Approved server-side batches. Persisted action state is authoritative."""
import hashlib
import json
import os
import boto3
from shared.db import get_item, put_item, query_pk, _get_table
from shared.utils import parse_body, response, now_iso

LOCAL = {'create_task','complete_task','create_journal','save_note','set_focus','update_task'}

def start(event, user_id):
    ids=parse_body(event).get('action_ids',[])
    if not isinstance(ids,list) or not 1<=len(ids)<=10 or any(not isinstance(x,str) for x in ids) or len(set(ids))!=len(ids):
        raise ValueError('Select one to ten different saved proposals.')
    items=[get_item(f'USER#{user_id}','ACTION#'+i) for i in ids]
    if any(not p or p['status'] not in ('pending','completed') for p in items):
        raise ValueError('Refresh your proposals; one is missing, running or needs review.')
    arn=os.environ.get('WORKFLOW_ARN')
    if not arn: raise ValueError('Background workflows are not configured yet.')
    wid=hashlib.sha256((user_id+json.dumps(sorted(ids))).encode()).hexdigest()[:32]
    key={'PK':f'USER#{user_id}','SK':'WORKFLOW#'+wid}
    # A repeated approval has the same execution name and exact input.
    item={**key,'workflow_id':wid,'action_ids':ids,'status':'approved','created_at':now_iso()}
    table=_get_table()
    try: table.put_item(Item=item,ConditionExpression='attribute_not_exists(PK)')
    except table.meta.client.exceptions.ConditionalCheckFailedException: pass
    saved=get_item(key['PK'],key['SK'])
    payload={'user_id':user_id,'workflow_id':wid,'steps':[{'user_id':user_id,'workflow_id':wid,'action_id':i} for i in saved['action_ids']]}
    client=boto3.client('stepfunctions',region_name=os.environ.get('REGION','us-east-2'))
    try: client.start_execution(stateMachineArn=arn,name=wid,input=json.dumps(payload,sort_keys=True))
    except client.exceptions.ExecutionAlreadyExists: pass
    return response(202,{'workflow_id':wid,'status':'accepted'})

def list_workflows(event,user_id):
    records=query_pk(f'USER#{user_id}','WORKFLOW#',limit=100)
    from shared.job_progress import public_job
    requests = [public_job(j) for j in query_pk(f'USER#{user_id}', 'JOB#', limit=1000) if j.get('status') in ('pending','processing')]
    requests = sorted(requests, key=lambda j:j.get('created_at') or '', reverse=True)[:3]
    output=[]
    for record in records:
        steps=[]
        for aid in record['action_ids']:
            p=get_item(f'USER#{user_id}','ACTION#'+aid) or {}
            steps.append({'action_id':aid,'status':p.get('status','missing'),'title':p.get('action',{}).get('title') or p.get('action',{}).get('action'),'result':p.get('result')})
        done=sum(s['status']=='completed' for s in steps)
        review=any(s['status'] in ('needs_review','failed','missing') for s in steps)
        status='completed' if done==len(steps) else 'needs_review' if review else 'running'
        output.append({'workflow_id':record['workflow_id'],'created_at':record['created_at'],'status':status,'completed':done,'total':len(steps),'steps':steps})
    return response(200,{'requests':requests, 'workflows':sorted(output,key=lambda x:x['created_at'],reverse=True)[:20], 'notifications':[{k:v for k,v in n.items() if k not in ('PK','SK')} for n in query_pk(f'USER#{user_id}','NOTICE#',limit=50)]})

def run_step(event):
    from api.routes import actions
    uid,wid,aid=event['user_id'],event['workflow_id'],event['action_id']
    workflow=get_item(f'USER#{uid}','WORKFLOW#'+wid)
    if not workflow or aid not in workflow.get('action_ids',[]): raise ValueError('No saved approval for this step.')
    proposal=get_item(f'USER#{uid}','ACTION#'+aid)
    if not proposal: raise ValueError('Proposal not found.')
    try:
        if proposal['status']=='pending':
            # Hold an owner/resource-specific lease, not a workspace-wide lease.
            from shared.planning_lock import agent_lock
            action=proposal['action']
            resource=action.get('page_id') or action.get('event_id') or action.get('task_id') or aid
            with agent_lock(uid, resource=hashlib.sha256(str(resource).encode()).hexdigest()):
                if action['action'] in LOCAL:
                    result=actions.confirm({'_path_params':{'id':aid}},uid)
                    if result['statusCode']>=400: raise ValueError(json.loads(result['body']).get('error',{}).get('message','Step failed'))
                else:
                    actions.execute_external(uid,{'action_id':aid})
    except Exception as exc:
        # Never reset a claimed/uncertain external write to pending.
        table=_get_table()
        try:
            table.update_item(Key={'PK':f'USER#{uid}','SK':'ACTION#'+aid},UpdateExpression='SET #s=:s, #r=:r',ConditionExpression='#s=:pending',ExpressionAttributeNames={'#s':'status','#r':'result'},ExpressionAttributeValues={':s':'needs_review',':pending':'pending',':r':{'message':str(exc)}})
        except table.meta.client.exceptions.ConditionalCheckFailedException: pass
    saved=get_item(f'USER#{uid}','ACTION#'+aid)
    return {'user_id':uid,'workflow_id':wid,'action_id':aid,'status':saved['status']}

def notification(event):
    detail=event.get('detail',{})
    uid,wid,aid=detail.get('user_id'),detail.get('workflow_id'),detail.get('action_id')
    workflow=get_item(f'USER#{uid}','WORKFLOW#'+str(wid))
    if not workflow or aid not in workflow.get('action_ids',[]): return {'ignored':True}
    if detail.get('status') == 'needs_review':
        table=_get_table()
        try:
            table.update_item(Key={'PK':f'USER#{uid}','SK':'ACTION#'+aid},UpdateExpression='SET #s=:review, #r=:result',ConditionExpression='#s IN (:pending,:processing)',ExpressionAttributeNames={'#s':'status','#r':'result'},ExpressionAttributeValues={':review':'needs_review',':pending':'pending',':processing':'processing',':result':{'message':'The background worker could not confirm this step. Check its destination before retrying.'}})
        except table.meta.client.exceptions.ConditionalCheckFailedException: pass
    step=get_item(f'USER#{uid}','ACTION#'+aid) or {}
    state=step.get('status','unknown')
    item={'PK':f'USER#{uid}','SK':f'NOTICE#{wid}#{aid}#{state}','workflow_id':wid,'action_id':aid,'status':state,'message':step.get('result',{}).get('message',state),'created_at':now_iso()}
    try: _get_table().put_item(Item=item,ConditionExpression='attribute_not_exists(PK)')
    except _get_table().meta.client.exceptions.ConditionalCheckFailedException: pass
    if state == 'completed' and step.get('action',{}).get('action') in ('create_task','update_task','complete_task'):
        from shared.notion_mirror import request_sync
        request_sync(uid)
    return {'recorded':True}
