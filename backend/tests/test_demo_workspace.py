import json
from unittest.mock import patch
import unittest
import test_sync_and_approvals as core
from shared import db
from shared.demo_workspace import seed, require_personal
from api.routes import integrations, actions, plan
from api.handler import _create_session

class DemoWorkspaceTests(unittest.TestCase):
    setUp=core.CoreTests.setUp
    tearDown=core.CoreTests.tearDown

    def test_each_visitor_gets_isolated_content_without_connections(self):
        first=json.loads(_create_session({'body':json.dumps({'demo_profile':'everyday','timezone':'America/Phoenix'})})['body'])
        second=json.loads(_create_session({'body':json.dumps({'demo_profile':'everyday','timezone':'America/Phoenix'})})['body'])
        self.assertNotEqual(first['user_id'],second['user_id'])
        self.assertNotEqual(first['token'],second['token'])
        for user in [first['user_id'],second['user_id']]:
            pk='USER#'+user
            self.assertEqual(len(db.query_pk(pk,'TASK#')),3)
            self.assertEqual(len(db.query_pk(pk,'HABIT#')),3)
            self.assertEqual(len(db.query_pk(pk,'DOC#')),3)
            self.assertEqual(len(db.query_pk(pk,'BLOCK#')),14)
            self.assertEqual(db.query_pk(pk,'INTEGRATION#'),[])

    def test_demo_cannot_connect_or_write_to_external_accounts(self):
        seed('demo','student','America/Phoenix')
        for start in [integrations.start_google_auth,integrations.start_notion_auth]:
            with self.assertRaisesRegex(ValueError,'Start clean'):
                start({},'demo')
        with self.assertRaisesRegex(ValueError,'sample page'):
            actions.create_proposal('demo',{'action':'notion_append','page_id':'arbitrary','text':'sample'})
        from shared.notion_mirror import request_sync
        with patch('boto3.client') as client:
            self.assertEqual(request_sync('demo')['status'],'disabled_in_demo')
        client.assert_not_called()

    def test_clean_session_has_no_sample_data_or_integrations(self):
        seed('demo','builder','America/Phoenix')
        clean=json.loads(_create_session()['body'])
        records=db.query_pk('USER#'+clean['user_id'])
        self.assertEqual([r['SK'] for r in records],['PROFILE'])
        self.assertFalse(records[0].get('sample_data'))
        require_personal(clean['user_id'])

    def test_sample_planning_context_is_labeled_and_not_google(self):
        seed('demo','everyday','America/Phoenix')
        tasks=db.query_pk('USER#demo','TASK#')
        records=db.query_pk('USER#demo')
        def index_records(index, pk, sk_prefix=None, **kwargs):
            return [r for r in records if r.get(index+'PK')==pk and r.get(index+'SK','').startswith(sk_prefix or '')]
        with patch('shared.agents.query_gsi',side_effect=index_records):
            context=plan.planning_context('demo',tasks[0]['due_date'])
        self.assertEqual(context['blockers'],[])
        self.assertFalse(context['google_connected'])
        self.assertIn('Sample schedule',context['warnings'][0])

    def test_sample_fallback_preserves_commitments_and_defers_overflow(self):
        from shared.demo_workspace import sample_plan
        from shared.plan_validation import validate
        tasks=[{'task_id':'one','title':'Short task','estimated_minutes':30},{'task_id':'two','title':'Too long','estimated_minutes':120}]
        existing=[{'source':'demo','locked':True,'start_time':'09:00','end_time':'10:00'}]
        result=sample_plan(tasks,existing,'09:00','11:00')
        validate(result['blocks'],existing)
        self.assertEqual(len(result['blocks']),1)
        self.assertEqual(result['blocks'][0]['start_time'],'10:00')
        self.assertIn('scheduling rules',result['explanation'])

    def test_sample_changes_need_approval_and_are_idempotent(self):
        from shared.demo_actions import page
        seed('demo','everyday','America/Phoenix')
        original=page('demo')['extracted_text']
        before=len(db.query_pk('USER#demo','BLOCK#'))
        with patch('shared.notion_tools.execute',side_effect=AssertionError('External Notion call')), patch('shared.agents._execute_chat_action',side_effect=AssertionError('External calendar call')):
            note=actions.create_proposal('demo',{'action':'notion_append','page_id':'demo-notion','text':'My approved checklist'})
            event=actions.create_proposal('demo',{'action':'create_event','calendar_id':'demo-calendar','date':'2026-10-17','start_time':'17:00','end_time':'17:30','title':'Walk'})
            self.assertEqual(page('demo')['extracted_text'],original)
            self.assertEqual(len(db.query_pk('USER#demo','BLOCK#')),before)
            for proposal in (note,event):
                for _ in range(2):
                    result=actions.execute_external('demo',{'action_id':proposal['action_id']})
                    self.assertEqual(result['status'],'completed')
                    self.assertTrue(result['result']['demo'])
            self.assertEqual(page('demo')['extracted_text'].count('My approved checklist'),1)
            self.assertEqual(len(db.query_pk('USER#demo','BLOCK#')),before+1)
            self.assertEqual(db.query_pk('USER#demo','INTEGRATION#'),[])
        self.assertEqual(actions.confirm({'_path_params':{'id':note['action_id']}},'someone-else')['statusCode'],404)

    def test_stale_demo_page_preview_cannot_overwrite_edits(self):
        seed('demo','everyday','America/Phoenix')
        one=actions.create_proposal('demo',{'action':'notion_append','text':'first'})
        two=actions.create_proposal('demo',{'action':'notion_append','text':'second'})
        actions.execute_external('demo',{'action_id':one['action_id']})
        with self.assertRaisesRegex(ValueError,'fresh preview'):
            actions.execute_external('demo',{'action_id':two['action_id']})

    def test_demo_calendar_rechecks_conflicts_before_completion(self):
        seed('demo','everyday','America/Phoenix')
        event={'action':'create_event','date':'2026-10-17','start_time':'17:00','end_time':'17:30','title':'Walk'}
        one=actions.create_proposal('demo',event)
        two=actions.create_proposal('demo',event)
        actions.execute_external('demo',{'action_id':one['action_id']})
        with self.assertRaisesRegex(ValueError,'conflicts'):
            actions.execute_external('demo',{'action_id':two['action_id']})

    def test_shopping_lookup_after_workflow_never_creates_proposal(self):
        from shared.agents import process_chat
        seed('demo','everyday','America/Phoenix')
        with patch('shared.agents.chat_turn', return_value='Eggs and milk [S1].') as answer, patch('shared.request_pipeline.run',side_effect=AssertionError('Read question entered write planner')):
            result=process_chat('demo',{'message':'What’s on my shopping list?'})
        self.assertEqual(result['proposals'],[])
        self.assertTrue(result['sources'])
        self.assertEqual(db.query_pk('USER#demo','ACTION#'),[])
        self.assertNotIn('history',answer.call_args.kwargs)
