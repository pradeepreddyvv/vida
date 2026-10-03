import json
import os
from unittest.mock import patch, MagicMock
import test_sync_and_approvals as core
import unittest
from shared import db, notion_tools
from api.routes import actions

PAGE='12345678-1234-1234-1234-123456789abc'
class AssistantToolsTests(unittest.TestCase):
    def setUp(self):
        core.CoreTests.setUp(self)
        # Legacy chat fallback tests isolate that path. Dedicated pipeline tests
        # exercise classification, coverage, and persisted clarification state.
        self.router_patch=patch('shared.request_pipeline.run',return_value=None)
        self.router_patch.start()
        self.addCleanup(self.router_patch.stop)
    tearDown=core.CoreTests.tearDown
    def test_two_provider_request_repairs_single_action_before_approval(self):
        from shared.agents import process_chat
        from shared.models import build_profile
        db.put_item(build_profile('a'))
        repaired={'action':'workflow','actions':[{'action':'create_event','title':'Demo'},{'action':'notion_append','page_id':PAGE,'text':'Demo'}]}
        with patch('shared.agents.query_gsi',return_value=[]), patch('shared.agents.chat_turn',return_value='{"action":"create_event","title":"Demo"}'), patch('shared.agents.converse_json',return_value=repaired) as repair, patch.object(actions,'create_workflow',return_value=[{'status':'pending'},{'status':'pending'}]) as create:
            result=process_chat('a',{'message':'Create a Google Calendar event and append a note in Notion.'})
            repair.assert_called_once()
            create.assert_called_once_with('a',repaired['actions'])
            self.assertEqual(len(result['proposals']),2)
    def test_workflow_keeps_both_steps_and_approves_independently(self):
        steps=actions.create_workflow('a',[{'action':'create_task','title':'Demo'},{'action':'save_note','title':'Decision','text':'Use verified sources'}])
        self.assertEqual(len(steps),2)
        self.assertIsNone(db.get_item('USER#a','TASK#'+steps[0]['action_id']))
        actions.confirm({'_path_params':{'id':steps[0]['action_id']}},'a')
        self.assertEqual(db.get_item('USER#a','ACTION#'+steps[0]['action_id'])['status'],'completed')
        self.assertEqual(db.get_item('USER#a','ACTION#'+steps[1]['action_id'])['status'],'pending')
        actions.confirm({'_path_params':{'id':steps[1]['action_id']}},'a')
        self.assertIsNotNone(db.get_item('USER#a','DOC#'+steps[1]['action_id']))
    def test_workflow_retains_blocked_step(self):
        steps=actions.create_workflow('a',[{'action':'create_task','title':'Demo'},{'action':'complete_task','task_id':'missing'}])
        self.assertEqual([p['status'] for p in steps],['pending','blocked'])
        self.assertIn('existing task',steps[1]['error'])
    def test_duration_normalizes_numeric_formats(self):
        from decimal import Decimal
        for value in (45, '45', 45.0, Decimal('45')):
            proposal=actions.create_proposal('a',{'action':'create_task','title':'Groceries','estimated_minutes':value})
            self.assertEqual(proposal['action']['estimated_minutes'],45)
            self.assertIsInstance(proposal['action']['estimated_minutes'],int)
        for value in (True, False, 'NaN', 'Infinity', 'bad', 0, 1441, 30.5):
            with self.assertRaises(ValueError):
                actions.create_proposal('a',{'action':'create_task','title':'Groceries','estimated_minutes':value})

    def test_approval_and_clear_never_invent_execution(self):
        from shared.agents import process_chat
        with patch('shared.agents.chat_turn') as model:
            result=process_chat('a',{'message':'approve all'})
            self.assertIn('no pending saved',result['reply'])
            result=process_chat('a',{'message':'clear all'})
            self.assertIn('Nothing has been cleared',result['reply'])
            model.assert_not_called()

    def test_prose_followup_becomes_real_proposals_with_history(self):
        from shared.agents import process_chat
        from shared.models import build_profile, build_chat_message
        db.put_item(build_profile('a'))
        db.put_item(build_chat_message('a','default','user','Make grocery shopping 45 minutes and save eggs and milk as a note.'))
        repaired={'action':'workflow','actions':[{'action':'create_task','title':'Groceries','estimated_minutes':'45'},{'action':'save_note','title':'Groceries','text':'eggs, milk'}]}
        with patch('shared.agents.query_gsi',return_value=[]), patch('shared.agents.chat_turn',return_value='Here is your complete workflow. Please approve all.'), patch('shared.agents.converse_json',return_value=repaired) as repair:
            result=process_chat('a',{'message':'Use my personal calendar'})
            self.assertEqual(len(result['proposals']),2)
            self.assertEqual([p['status'] for p in result['proposals']],['pending','pending'])
            self.assertIn('eggs and milk',str(repair.call_args))
            self.assertEqual(db.query_pk('USER#a','TASK#'),[])

    def test_calendar_outside_synced_window_is_blocked(self):
        db.put_item({'PK':'USER#a','SK':'INTEGRATION#google_calendar','status':'connected','selected_calendars':['primary'],'synced_from':'2026-10-02','synced_until':'2026-10-09'})
        with self.assertRaisesRegex(ValueError,'outside your imported'):
            actions.create_proposal('a',{'action':'create_event','title':'Walk','calendar_id':'primary','date':'2026-10-17','start_time':'17:00','end_time':'17:30'})

    def seed(self):
        db.put_item({'PK':'USER#a','SK':'DOC#notion-'+PAGE,'source':'notion','notion_id':PAGE,'file_name':'Demo'})
        db.put_item({'PK':'USER#a','SK':'INTEGRATION#notion','status':'connected','access_token':'test'})
    def test_notion_owner_boundary(self):
        self.seed()
        with patch.object(notion_tools,'_request') as request:
            with self.assertRaisesRegex(ValueError,'not in your synced'): notion_tools.snapshot('b',PAGE)
            request.assert_not_called()
    def test_empty_notion_catalog_bypasses_model(self):
        from shared.agents import process_chat
        from shared.models import build_profile
        db.put_item(build_profile('a'))
        with patch('shared.agents.chat_turn') as model, patch('shared.agents.query_gsi',return_value=[]):
            result=process_chat('a',{'message':'Append a note to Notion page Vida demo test'})
            self.assertIn('No shared Notion pages',result['reply'])
            self.assertIsNone(result['proposal'])
            model.assert_not_called()
    def test_replace_rejects_nested_content(self):
        with patch.object(notion_tools,'snapshot',return_value={'has_more':False,'text':'old','blocks':[{'type':'child_page','has_children':True}]}):
            with self.assertRaisesRegex(ValueError,'richer content'): notion_tools.prepare('a',{'action':'notion_replace','page_id':PAGE,'text':'new'})
    def test_create_private_workspace_page_without_parent(self):
        db.put_item({'PK':'USER#a','SK':'INTEGRATION#notion','status':'connected','access_token':'test'})
        action=notion_tools.prepare('a',{'action':'notion_create','workspace':True,'title':'Demo','text':'test note'})
        with patch.object(notion_tools,'snapshot') as snapshot, patch.object(notion_tools,'_request',side_effect=[{'id':PAGE,'url':'https://notion.so/'+PAGE},{'results':[]}]) as request:
            result=notion_tools.execute('a',action)
            snapshot.assert_not_called()
            self.assertEqual(request.call_args_list[0].args[2]['parent'],{'workspace':True})
            self.assertEqual(result['page_id'],PAGE)
    def test_stale_notion_preview_never_writes(self):
        with patch.object(notion_tools,'snapshot',return_value={'signature':'changed'}), patch.object(notion_tools,'_request') as request:
            with self.assertRaisesRegex(ValueError,'changed since'): notion_tools.execute('a',{'action':'notion_append','page_id':PAGE,'_signature':'old','text':'new'})
            request.assert_not_called()
    def test_append_and_refresh_index(self):
        self.seed()
        snap={'signature':'same','title':'Demo','url':'https://www.notion.so/'+PAGE,'blocks':[]}
        results=[{'results':[]},{'results':[{'type':'paragraph','paragraph':{'rich_text':[{'plain_text':'new note'}]}}]}]
        with patch.object(notion_tools,'snapshot',return_value=snap), patch.object(notion_tools,'_request',side_effect=results) as request:
            result=notion_tools.execute('a',{'action':'notion_append','page_id':PAGE,'_signature':'same','text':'new note'})
            self.assertEqual(request.call_args_list[0].args[-1],'PATCH')
            self.assertEqual(result['destination'],'Notion')
        doc=db.get_item('USER#a','DOC#notion-'+PAGE)
        self.assertEqual(doc['extracted_text'],'new note'); self.assertEqual(doc['kb_status'],'indexed')
    def test_external_confirmation_is_idempotent(self):
        db.put_item({'PK':'USER#a','SK':'ACTION#one','status':'pending','action':{'action':'notion_append'}})
        with patch.object(notion_tools,'execute',return_value={'message':'Done'}) as execute:
            actions.execute_external('a',{'action_id':'one'})
            actions.execute_external('a',{'action_id':'one'})
            self.assertEqual(execute.call_count,1)
    def test_uncertain_external_result_is_not_success(self):
        db.put_item({'PK':'USER#a','SK':'ACTION#one','status':'pending','action':{'action':'notion_append'}})
        with patch.object(notion_tools,'execute',side_effect=TimeoutError('Timed out')):
            with self.assertRaisesRegex(ValueError,'Could not confirm'): actions.execute_external('a',{'action_id':'one'})
        self.assertEqual(db.get_item('USER#a','ACTION#one')['status'],'needs_review')
    def test_no_web_key_is_not_fake_research(self):
        with patch.dict(os.environ,{'TAVILY_API_KEY':''}):
            with self.assertRaisesRegex(ValueError,'Tavily API key'): actions.create_proposal('a',{'action':'web_search','query':'weather'})
    def test_note_and_focus_approval(self):
        from shared.models import build_profile, build_task
        db.put_item(build_profile('a'))
        db.put_item(build_task('a',task_id='one',title='Demo'))
        proposal=actions.create_proposal('a',{'action':'set_focus','task_ids':['one']})
        self.assertEqual(db.get_item('USER#a','PROFILE')['planning_focus_task_ids'],[])
        result=actions.confirm({'_path_params':{'id':proposal['action_id']}},'a')
        self.assertEqual(result['statusCode'],200)
        self.assertEqual(db.get_item('USER#a','PROFILE')['planning_focus_task_ids'],['one'])

    def test_action_with_intro_still_creates_a_reviewable_proposal(self):
        from shared.agents import _extract_action
        action, _ = _extract_action('Here is a proposal:\n\n{"action":"create_task","title":"Demo {draft}","estimated_minutes":20}\nPlease review.')
        self.assertEqual(action['title'],'Demo {draft}')
    def test_model_echoed_completed_status_is_only_a_new_action(self):
        from shared.agents import _extract_action
        action, _ = _extract_action('Recorded proposal status: {"status":"completed","action":{"action":"notion_create","workspace":true,"title":"Demo","text":"test"}}')
        self.assertEqual(action['action'],'notion_create')
        self.assertNotIn('status',action)
    def test_separate_action_objects_become_one_workflow(self):
        from shared.agents import _extract_action
        action,_ = _extract_action('{"action":"create_task","title":"Demo"}\n{"action":"save_note","title":"Note","text":"Remember"}')
        self.assertEqual(action['action'],'workflow')
        self.assertEqual(len(action['actions']),2)

    def test_destination_reply_to_priority_question_preserves_approval(self):
        from shared.agents import process_chat
        from shared.models import build_chat_message
        db.put_item(build_chat_message('a','default','assistant','Which open tasks would you like to prioritize? Choose from demo and sorting.'))
        context={'tasks':[{'task_id':'one','title':'demo','estimated_minutes':30}], 'profile':{'name':'Test','role':''}, 'goals':[], 'habits':[], 'existing_blocks':[]}
        with patch('shared.agents._get_user_context',return_value=context), patch('shared.agents.chat_turn') as model:
            result=process_chat('a',{'message':'For my earlier request, use these destinations: Google calendar: me@example.com. Notion page: Notes.'})
        model.assert_not_called()
        self.assertIn('demo — 30 minutes',result['reply'])
        self.assertIn('approval before saving',result['reply'])
        self.assertEqual(result['proposals'],[])
        self.assertEqual(db.query_pk('USER#a','ACTION#'),[])

    def test_task_name_reply_proposes_focus_not_duplicate_tasks(self):
        from shared.agents import process_chat
        from shared.models import build_chat_message, build_task
        task=build_task('a',title='demo',estimated_minutes=30)
        db.put_item(task)
        db.put_item(build_chat_message('a','default','assistant','Which open tasks would you like to prioritize?'))
        context={'tasks':[{'task_id':task['SK'][5:],'title':'demo','estimated_minutes':30}], 'profile':{'name':'Test','role':''}, 'goals':[], 'habits':[], 'existing_blocks':[]}
        with patch('shared.agents._get_user_context',return_value=context), patch('shared.agents.chat_turn') as model:
            result=process_chat('a',{'message':'demo first please'})
        model.assert_not_called()
        self.assertEqual(result['proposals'][0]['action']['action'],'set_focus')
        self.assertEqual(result['proposals'][0]['status'],'pending')
        self.assertEqual(len(db.query_pk('USER#a','TASK#')),1)
