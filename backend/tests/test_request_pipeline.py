import unittest
from unittest.mock import patch
import test_sync_and_approvals as core
from shared import request_pipeline as pipeline, db
from api.routes import actions

class RequestPipelineTests(unittest.TestCase):
    setUp=core.CoreTests.setUp
    tearDown=core.CoreTests.tearDown
    def item(self, id='i1',kind='create_task',minutes=45):
        return {'id':id,'kind':kind,'summary':'Groceries','evidence':'groceries','minutes':minutes,'date':'2026-10-17','content_points':[]}
    def test_unnumbered_request_becomes_two_saved_steps(self):
        items=[self.item(),self.item('i2','save_note',None)]
        planned={'steps':[{'item_id':'i1','action':{'action':'create_task','title':'Groceries','estimated_minutes':45,'due_date':'2026-10-17'}},{'item_id':'i2','action':{'action':'save_note','title':'Shopping list','text':'eggs and milk'}}]}
        with patch.object(pipeline,'_model',side_effect=[{'mode':'new','items':items},planned]):
            result=pipeline.run('a','default','Buy groceries and save eggs and milk.','',[])
        self.assertEqual(len(result['proposals']),2)
        self.assertEqual(db.query_pk('USER#a','TASK#'),[])
    def test_coverage_rejects_dropped_and_extra_steps(self):
        for steps in ([],[{'item_id':'i2','clarification':'Which page?'}],[{'item_id':'i1','clarification':'Which?'},{'item_id':'i1','clarification':'Which?'}]):
            with self.assertRaises(ValueError): pipeline.review([self.item()],{'steps':steps})
    def test_event_duration_cannot_change(self):
        item=self.item(kind='create_event',minutes=30)
        with self.assertRaisesRegex(ValueError,'event duration'):
            pipeline.review([item],{'steps':[{'item_id':'i1','action':{'action':'create_event','date':'2026-10-17','start_time':'17:00','end_time':'18:00'}}]})
    def test_short_clarification_cannot_drop_original_items(self):
        with self.assertRaisesRegex(ValueError,'lost part'):
            pipeline.validate_items({'mode':'continue','items':[self.item()]},{'items':[self.item(),self.item('i2')]})
    def test_completed_step_not_repeated_on_followup(self):
        item=self.item()
        p=actions.create_proposal('a',{'action':'create_task','title':'Groceries','estimated_minutes':45})
        actions.confirm({'_path_params':{'id':p['action_id']}},'a')
        db.put_item({'PK':'USER#a','SK':'REQUEST#default','request_id':'r','items':[item],'user_messages':['Groceries please'],'proposals':{'i1':p['action_id']}})
        with patch.object(pipeline,'_model',return_value={'mode':'continue','items':[item]}) as model:
            result=pipeline.run('a','default','yes that one','',[])
        self.assertEqual(model.call_count,1)
        self.assertEqual(result['proposals'][0]['status'],'completed')
        self.assertEqual(len(db.query_pk('USER#a','TASK#')),1)
    def test_question_does_not_create_proposal(self):
        with patch.object(pipeline,'_model',return_value={'mode':'question','items':[]}):
            self.assertIsNone(pipeline.run('a','default','What is on my calendar?','',[]))
        self.assertEqual(db.query_pk('USER#a','ACTION#'),[])

    def test_email_clarification_does_not_use_model_or_drop_items(self):
        items=[self.item(),self.item('i2','save_note',None)]
        with patch.object(pipeline,'_model') as model:
            result=pipeline.classify('me@example.com for all',{'items':items},[],'2026-10-02')
        model.assert_not_called()
        self.assertEqual(result,{'mode':'continue','items':items})

    def test_classifier_repairs_invalid_item_list_once(self):
        expected={'mode':'new','items':[self.item()]}
        with patch.object(pipeline,'_model',side_effect=[{'mode':'new','items':[]},expected]) as model:
            self.assertEqual(pipeline.classify('groceries for 45 minutes',{},[],'2026-10-02'),expected)
        self.assertEqual(model.call_count,2)

    def test_checklist_cannot_be_reduced_to_heading(self):
        item=self.item(kind='notion_append',minutes=None)
        item['content_points']=['groceries','laundry','walk']
        with self.assertRaisesRegex(ValueError,'checklist entries'):
            pipeline.review([item],{'steps':[{'item_id':'i1','action':{'action':'notion_append','text':'Saturday reset checklist'}}]})

    def test_non_object_model_outputs_fail_closed(self):
        for bad in (None, [], 'done'):
            with self.assertRaises(ValueError): pipeline.validate_items(bad,{})
            with self.assertRaises(ValueError): pipeline.review([self.item()],bad)
            with self.assertRaises(ValueError): pipeline.review([self.item()],{'steps':[{'item_id':'i1','action':bad}]})
        with patch.object(pipeline,'_model',return_value=[]) as model:
            with self.assertRaises(ValueError): pipeline.classify('do laundry',{},[],'2026-10-02')
        self.assertEqual(model.call_count,2)

    def test_six_to_ten_intents_are_not_rejected(self):
        items=[self.item('i'+str(i)) for i in range(10)]
        self.assertEqual(len(pipeline.validate_items({'mode':'new','items':items},{})),10)
        with self.assertRaises(ValueError):
            pipeline.validate_items({'mode':'new','items':items+[self.item('overflow')]},{})

    def test_malformed_json_repair_does_not_force_continuation(self):
        expected={'mode':'new','items':[self.item()]}
        with patch.object(pipeline,'_model',side_effect=[ValueError('Malformed JSON'),expected]) as model:
            self.assertEqual(pipeline.classify('Organize October 24',{},[],'2026-10-02'),expected)
        self.assertIn('use new for a complete new request',model.call_args.args[1]['repair_instruction'])

    def test_preview_request_cannot_silently_drop_valid_write_items(self):
        with patch.object(pipeline,'_model',return_value={'mode':'question','items':[self.item()]}):
            result=pipeline.classify('Show a grocery task for approval',{},[],'2026-10-02')
        self.assertEqual(result['mode'],'new')
        self.assertEqual(len(result['items']),1)

    def test_demo_calendar_clarification_resolves_to_local_pending_slot(self):
        from shared.demo_workspace import seed
        seed('a','everyday','America/Phoenix')
        item=self.item(kind='create_event',minutes=30)
        with patch.object(pipeline,'_model',side_effect=[{'mode':'new','items':[item]},{'steps':[{'item_id':'i1','clarification':'Check availability in the selected calendar and propose a time slot.'}]}]):
            result=pipeline.run('a','default','Find a free half hour for a walk between 5 PM and 8 PM','',[])
        proposal=result['proposals'][0]
        self.assertEqual(proposal['status'],'pending')
        self.assertEqual(proposal['action']['start_time'],'17:00')
        self.assertEqual(proposal['action']['end_time'],'17:30')
        self.assertTrue(proposal['action']['_demo'])
        self.assertEqual(len(db.query_pk('USER#a','BLOCK#')),14)
