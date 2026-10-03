import os
import sys
import unittest
import hashlib
import time
from decimal import Decimal
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
os.environ.update(AWS_ACCESS_KEY_ID='testing', AWS_SECRET_ACCESS_KEY='testing', AWS_DEFAULT_REGION='us-east-2', REGION='us-east-2', TABLE_NAME='vida-test')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'functions'))
import boto3
from moto import mock_aws
from shared import db
from shared.utils import get_user_id, response
from shared.retrieval import retrieve_documents
from api.routes import actions, integrations

class CoreTests(unittest.TestCase):
    def test_full_day_is_warning_not_planning_blocker(self):
        from api.routes import plan
        from shared import agents
        ctx = {'profile': {'planning_focus_task_ids':['t'], 'day_start':'09:00', 'day_end':'17:00', 'timezone':'UTC'}, 'tasks':[{'task_id':'t'}], 'existing_blocks':[{'source':'google','start_time':'09:00','end_time':'17:00'}]}
        integration = {'status':'connected','selected_calendars':['primary'],'last_synced_at':'now','sync_status':'complete'}
        with patch.object(agents, '_get_user_context', return_value=ctx), patch.object(plan, 'get_item', return_value=integration), patch.object(plan, 'today_str', return_value='2026-10-02'):
            result = plan.planning_context('a', '2026-10-03')
        self.assertEqual(result['available_minutes'], 0)
        self.assertEqual(result['blockers'], [])
        self.assertTrue(result['warnings'])

    def test_zero_capacity_draft_defers_without_model_or_calendar_writes(self):
        from api.routes import plan
        from shared import agents
        ctx = {'profile':{'planning_focus_task_ids':['t']}, 'tasks':[{'task_id':'t','title':'Exercise'}], 'goals':[], 'existing_blocks':[]}
        context = {'blockers':[], 'day_start':'22:00','day_end':'17:00','available_minutes':0}
        with patch.object(integrations,'sync_google_calendar_worker'), patch.object(plan,'planning_context',return_value=context), patch.object(agents,'_get_user_context',return_value=ctx), patch('shared.retrieval.retrieve_documents',return_value=[]), patch.object(agents,'converse_json') as model:
            result = agents.process_plan_generate('a', {'date':'2026-10-02'})
        model.assert_not_called()
        self.assertEqual(result['plan']['blocks'], [])
        self.assertEqual(result['plan']['deferred_tasks'][0]['task_id'], 't')
        self.assertEqual(db.query_pk('USER#a','BLOCK#'), [])

    def test_onboarding_read_failure_is_not_reported_as_empty_text(self):
        from shared import agents
        with patch.object(agents, '_extract_text_from_s3', side_effect=RuntimeError('storage failure')), patch.object(agents, 'converse_json') as ai:
            with self.assertRaisesRegex(ValueError, 'Could not read your uploaded document'):
                agents.process_onboard('a', {'doc_id':'d', 's3_key':'uploads/a/d/source.pdf'})
            ai.assert_not_called()
        with patch.object(agents, '_extract_text_from_s3', return_value=''):
            result = agents.process_onboard('a', {'doc_id':'d', 's3_key':'uploads/a/d/source.pdf'})
            self.assertIn('selectable text', result['error'])
    def setUp(self):
        self.mock = mock_aws(); self.mock.start()
        db._table = boto3.resource('dynamodb', region_name='us-east-2').create_table(TableName='vida-test', KeySchema=[{'AttributeName':'PK','KeyType':'HASH'},{'AttributeName':'SK','KeyType':'RANGE'}], AttributeDefinitions=[{'AttributeName':'PK','AttributeType':'S'},{'AttributeName':'SK','AttributeType':'S'}], BillingMode='PAY_PER_REQUEST')
    def tearDown(self):
        db._table = None; self.mock.stop()
    def test_numbers_remain_numbers(self):
        db.put_item({'PK':'x','SK':'x','a':Decimal('1.25'),'nested':[2.5]})
        item=db.get_item('x','x')
        self.assertEqual(item['a'],Decimal('1.25'))
        self.assertIn('1.25',response(200,item)['body'])
        self.assertEqual(item['nested'],[Decimal('2.5')])
    def test_auth_rejects_forgery_and_expiry(self):
        self.assertIsNone(get_user_id({'headers':{'X-User-Id':'victim'}}))
        key='TOKEN#'+hashlib.sha256(b'test-token').hexdigest()
        db.put_item({'PK':'SESSIONS','SK':key,'user_id':'a','expires_at_epoch':int(time.time())+60})
        self.assertEqual(get_user_id({'headers':{'authorization':'Bearer test-token'}}),'a')
        db.update_item('SESSIONS',key,{'expires_at_epoch':0})
        self.assertIsNone(get_user_id({'headers':{'Authorization':'Bearer test-token'}}))
    def test_action_requires_owner_confirmation_and_is_idempotent(self):
        proposal=actions.create_proposal('a',{'action':'create_task','title':'Review notes'})
        self.assertEqual(db.query_pk('USER#a','TASK#'),[])
        event={'_path_params':{'id':proposal['action_id']}}
        self.assertEqual(actions.confirm(event,'b')['statusCode'],404)
        self.assertEqual(actions.confirm(event,'a')['statusCode'],200)
        self.assertEqual(actions.confirm(event,'a')['statusCode'],200)
        self.assertEqual(len(db.query_pk('USER#a','TASK#')),1)
    def test_retrieval_owner_tail_and_disconnected_notion(self):
        for owner in ['a','b']:
            db.put_item({'PK':'USER#'+owner,'SK':'DOC#one','extracted_text':'padding '*500+' uniquequartz '+owner,'kb_status':'indexed'})
        rows=retrieve_documents('a','uniquequartz')
        self.assertTrue(rows); self.assertTrue(all('uniquequartz a' in r['passage'] for r in rows))
        db.put_item({'PK':'USER#a','SK':'DOC#notion','source':'notion','extracted_text':'privateopal','kb_status':'indexed'})
        self.assertEqual(retrieve_documents('a','privateopal'),[])
    def test_calendar_pagination_midnight_and_deletion(self):
        today=datetime.now(timezone.utc).date()
        tomorrow=today+timedelta(days=1)
        db.put_item({'PK':'USER#a','SK':'INTEGRATION#google_calendar','status':'connected','selected_calendars':['primary']})
        db.put_item({'PK':'USER#a','SK':'BLOCK#gcal-obsolete','date':str(today)})
        pages=[{'items':[], 'nextPageToken':'next'}, {'items':[{'id':'full-event-id','summary':'Overnight','start':{'dateTime':f'{today}T23:00:00Z'},'end':{'dateTime':f'{tomorrow}T01:00:00Z'}}]}]
        with patch.object(integrations,'_refresh_google_token',return_value='fake'),patch.object(integrations,'_http_request',side_effect=pages) as http:
            result=integrations.sync_google_calendar_worker('a')
        self.assertEqual(http.call_count,2)
        self.assertEqual(result['synced_events'],2)
        self.assertEqual(result['removed_events'],1)
        blocks=db.query_pk('USER#a','BLOCK#')
        self.assertEqual(blocks[0]['end_time'],'24:00')
        self.assertEqual(blocks[1]['start_time'],'00:00')
        self.assertTrue(all(b['google_event_id']=='full-event-id' for b in blocks))

    def test_notion_nested_content_and_pagination(self):
        db.put_item({'PK':'USER#a','SK':'INTEGRATION#notion','status':'connected','access_token':'fake'})
        pages=[{'results':[{'id':'page-1','properties':{'Name':{'type':'title','title':[{'plain_text':'Notes'}]}}}], 'has_more':False},
               {'results':[{'id':'nested','type':'paragraph','paragraph':{'rich_text':[{'plain_text':'Parent'}]},'has_children':True}], 'has_more':True,'next_cursor':'page2'},
               {'results':[{'id':'tail','type':'paragraph','paragraph':{'rich_text':[{'plain_text':'Tail'}]}}], 'has_more':False},
               {'results':[{'id':'child','type':'paragraph','paragraph':{'rich_text':[{'plain_text':'Nested insight'}]}}], 'has_more':False}]
        with patch.object(integrations,'_http_request',side_effect=pages), patch.object(integrations.time,'sleep'):
            result=integrations.sync_notion_worker('a')
        self.assertFalse(result['partial'])
        doc=db.get_item('USER#a','DOC#notion-page-1')
        self.assertEqual(doc['extracted_text'],'Parent\nTail\nNested insight\n')
        self.assertIsNone(db.get_item('USER#a','SYNC#notion'))
    def test_oauth_provider_mismatch_does_not_consume_state(self):
        db.put_item({'PK':'OAUTH_STATE','SK':'STATE#test','provider':'notion','user_id':'a','expires_at_epoch':int(time.time())+60})
        result=integrations.google_callback({'queryStringParameters':{'state':'test','code':'fake'}},None)
        self.assertIn('invalid_state',result['headers']['Location'])
        self.assertIsNotNone(db.get_item('OAUTH_STATE','STATE#test'))

    def test_schedule_rejects_overlap_and_protected_move(self):
        from shared.plan_validation import validate
        with self.assertRaises(ValueError):
            validate([{'start_time':'09:00','end_time':'10:00'},{'start_time':'09:30','end_time':'11:00'}],[])
        with self.assertRaises(ValueError):
            validate([{'block_id':'x','start_time':'10:00','end_time':'11:00'}],[{'block_id':'x','start_time':'09:00','end_time':'10:00','locked':True}])
    def test_note_project_ownership(self):
        from api.routes.documents import create_note
        with self.assertRaises(ValueError):
            create_note({'body':{'title':'Note','text':'Text','goal_id':'someone-else'}},'a')
    def test_action_json_handles_braces_in_title(self):
        from shared.agents import _extract_action
        action, rest = _extract_action('{"action":"create_task","title":"Fix } parser"} Review this')
        self.assertEqual(action['title'],'Fix } parser')
        self.assertEqual(rest,'Review this')

if __name__=='__main__': unittest.main()

class ProviderAndPlanningTests(unittest.TestCase):
    setUp = CoreTests.setUp
    tearDown = CoreTests.tearDown
    def test_provider_unreadable_response_retries_and_explains(self):
        from unittest.mock import MagicMock
        res = MagicMock(); res.__enter__.return_value = res; res.read.return_value = b'<html>unavailable</html>'
        with patch.object(integrations.urllib.request, 'urlopen', return_value=res) as request, patch.object(integrations.time,'sleep'):
            with self.assertRaisesRegex(ValueError, 'Notion returned an unreadable response'):
                integrations._http_request('https://api.notion.com/v1/search')
            self.assertEqual(request.call_count,2)
    def test_single_workspace_agent_lock(self):
        from shared.planning_lock import agent_lock
        with agent_lock('a'):
            with self.assertRaisesRegex(ValueError, 'already processing'):
                with agent_lock('a'): pass
            with agent_lock('b'): pass
        with agent_lock('a'): pass
    def test_planning_requires_calendar_and_explicit_focus(self):
        from api.routes.plan import planning_context
        from shared import agents
        ctx={'profile':{'planning_focus_task_ids':[],'day_start':'09:00','day_end':'17:00','timezone':'UTC'},'tasks':[],'existing_blocks':[]}
        tomorrow=(datetime.now(timezone.utc)+timedelta(days=1)).date().isoformat()
        with patch.object(agents,'_get_user_context',return_value=ctx):
            result=planning_context('a',tomorrow)
        self.assertTrue(any('Connect Google' in x for x in result['blockers']))
        self.assertTrue(any('prioritize' in x for x in result['blockers']))
    def test_single_planner_preserves_commitments_and_uses_chosen_tasks(self):
        from shared import agents
        from api.routes import plan
        from shared.models import build_profile
        date=(datetime.now(timezone.utc)+timedelta(days=1)).date().isoformat()
        db.put_item(build_profile('a', planning_focus_task_ids=['t']))
        ctx={'profile':{'planning_focus_task_ids':['t'],'day_start':'09:00','day_end':'17:00','timezone':'UTC'},'tasks':[{'task_id':'t','title':'Chosen task'}],'goals':[], 'existing_blocks':[{'block_id':'busy','source':'google_calendar','locked':True,'start_time':'09:00','end_time':'10:00'}]}
        context={**ctx,'blockers':[],'day_start':'09:00','day_end':'17:00','available_minutes':420}
        with patch.object(integrations,'sync_google_calendar_worker'), patch.object(plan,'planning_context',return_value=context), patch.object(agents,'_get_user_context',return_value=ctx), patch.object(agents,'converse_json',return_value={'blocks':[{'block_type':'task','task_id':'t','title':'Wrong title','start_time':'10:00','end_time':'10:30'}]}) as ai:
            result=agents.process_plan_generate('a',{'date':date})
            self.assertEqual(ai.call_count,1)
            self.assertEqual(result['plan']['blocks'][0]['title'],'Chosen task')
            self.assertEqual(result['plan']['total_available_minutes'],420)
            ai.return_value={'blocks':[{'block_type':'task','task_id':'t','start_time':'09:00','end_time':'09:30'}]}
            with self.assertRaisesRegex(ValueError,'conflicts'): agents.process_plan_generate('a',{'date':date})
