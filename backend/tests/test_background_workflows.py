import json
import os
import unittest
from unittest.mock import patch, MagicMock
import test_sync_and_approvals as core
from shared import db
from api.routes import actions, workflows


class BackgroundWorkflowTests(unittest.TestCase):
    setUp=core.CoreTests.setUp
    tearDown=core.CoreTests.tearDown

    def test_approval_is_owner_scoped(self):
        p=actions.create_proposal('a',{'action':'create_task','title':'Demo'})
        with self.assertRaises(ValueError):
            workflows.start({'body':json.dumps({'action_ids':[p['action_id']]})},'b')

    def test_saved_batch_executes_without_browser_and_notifications_dedupe(self):
        steps=actions.create_workflow('a',[{'action':'create_task','title':'Demo'},{'action':'save_note','title':'Note','text':'test'}])
        client=MagicMock()
        with patch.dict(os.environ,{'WORKFLOW_ARN':'arn:test'}),patch.object(workflows.boto3,'client',return_value=client):
            result=workflows.start({'body':json.dumps({'action_ids':[p['action_id'] for p in steps]})},'a')
        self.assertEqual(result['statusCode'],202)
        payload=json.loads(client.start_execution.call_args.kwargs['input'])
        for step in payload['steps']:
            result=workflows.run_step(step)
            self.assertEqual(result['status'],'completed')
            workflows.run_step(step)
            workflows.notification({'detail':result})
            workflows.notification({'detail':result})
        view=json.loads(workflows.list_workflows({},'a')['body'])
        self.assertEqual(view['workflows'][0]['completed'],2)
        self.assertEqual(len(view['notifications']),2)
        self.assertEqual(len(db.query_pk('USER#a','TASK#')),1)

    def test_unapproved_step_cannot_run(self):
        with self.assertRaisesRegex(ValueError,'No saved approval'):
            workflows.run_step({'user_id':'a','workflow_id':'missing','action_id':'missing'})

    def test_late_error_event_does_not_overwrite_success(self):
        db.put_item({'PK':'USER#a','SK':'WORKFLOW#w','action_ids':['one']})
        db.put_item({'PK':'USER#a','SK':'ACTION#one','status':'completed','result':{'message':'Done'}})
        workflows.notification({'detail':{'user_id':'a','workflow_id':'w','action_id':'one','status':'needs_review'}})
        self.assertEqual(db.get_item('USER#a','ACTION#one')['status'],'completed')

    def test_ten_saved_steps_can_be_approved_as_one_batch(self):
        proposals=actions.create_workflow('a',[{'action':'create_task','title':'Task '+str(i)} for i in range(10)])
        ids=[p['action_id'] for p in proposals]
        client=MagicMock()
        with patch.dict(os.environ,{'WORKFLOW_ARN':'arn:test'}),patch.object(workflows.boto3,'client',return_value=client):
            result=workflows.start({'body':json.dumps({'action_ids':ids})},'a')
        self.assertEqual(result['statusCode'],202)
        payload=json.loads(client.start_execution.call_args.kwargs['input'])
        self.assertEqual(len(payload['steps']),10)
        self.assertEqual(db.query_pk('USER#a','TASK#'),[])
        with self.assertRaises(ValueError):
            workflows.start({'body':json.dumps({'action_ids':ids+['extra']})},'a')
