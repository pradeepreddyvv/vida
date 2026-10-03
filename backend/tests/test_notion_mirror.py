import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from copy import deepcopy
os.environ.update(AWS_ACCESS_KEY_ID='testing',AWS_SECRET_ACCESS_KEY='testing',AWS_DEFAULT_REGION='us-east-2',REGION='us-east-2',TABLE_NAME='vida-test')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'functions'))
import boto3
from moto import mock_aws
from shared import db, notion_mirror as mirror


class MirrorTests(unittest.TestCase):
    def setUp(self):
        self.aws=mock_aws(); self.aws.start()
        db._table=boto3.resource('dynamodb').create_table(TableName='vida-test',KeySchema=[{'AttributeName':'PK','KeyType':'HASH'},{'AttributeName':'SK','KeyType':'RANGE'}],AttributeDefinitions=[{'AttributeName':'PK','AttributeType':'S'},{'AttributeName':'SK','AttributeType':'S'}],BillingMode='PAY_PER_REQUEST')
        db.put_item({'PK':'USER#a','SK':'INTEGRATION#notion','status':'connected','workspace_id':'w','access_token':'test'})
        self.pages={}; self.blocks={}; self.serial=0
        self.http=patch.object(mirror,'_request',side_effect=self.request); self.http.start()
        self.sleep=patch.object(mirror.time,'sleep'); self.sleep.start()
    def tearDown(self):
        self.http.stop(); self.sleep.stop(); db._table=None; self.aws.stop()
    def request(self,uid,path,data=None,method='GET'):
        self.assertEqual(uid,'a')
        self.serial+=1
        if path=='pages':
            pid='p'+str(len(self.pages)+1)
            self.pages[pid]={'id':pid,'url':'https://www.notion.so/'+pid}
            self.blocks[pid]=[]
            return self.pages[pid]
        if path.startswith('pages/'):
            return self.pages[path.split('/')[1]]
        pid=path.split('/')[1]
        if '/children' in path:
            if method=='GET': return {'results':deepcopy(self.blocks[pid]),'has_more':False}
            created=[]
            for child in data['children']:
                child=deepcopy(child); child['id']='b'+str(self.serial)
                self.blocks[pid].append(child); created.append(child)
            return {'results':created}
        for children in self.blocks.values():
            for b in children:
                if b['id']==pid: b.update(deepcopy(data)); return b
        raise AssertionError(path)
    def seed(self):
        db.put_item({'PK':'USER#a','SK':'TASK#t','title':'Groceries','status':'todo','due_date':'2026-10-03'})
        db.put_item({'PK':'USER#a','SK':'HABIT#h','name':'Walk','frequency':'daily'})
        db.put_item({'PK':'USER#a','SK':'HABITLOG#2026-10-03#h','completed':True})
    def test_repeat_and_completion_preserve_manual_notes(self):
        self.seed(); mirror.sync('a')
        self.blocks['p1'].append({'id':'manual','type':'paragraph','paragraph':{'rich_text':[{'text':{'content':'Keep my own notes'}}]}})
        mirror.sync('a'); self.assertEqual(len(self.pages),2); self.assertEqual(len(self.blocks['p1']),2)
        task=db.get_item('USER#a','TASK#t'); task['status']='done'; db.put_item(task)
        mirror.sync('a'); self.assertTrue(self.blocks['p1'][0]['to_do']['checked'])
        self.assertEqual(self.blocks['p1'][1]['paragraph']['rich_text'][0]['text']['content'],'Keep my own notes')
        self.assertTrue(self.blocks['p2'][1]['to_do']['checked'])
        db.delete_item('USER#a','TASK#t'); mirror.sync('a')
        self.assertTrue(self.blocks['p1'][0]['archived']); self.assertNotIn('archived',self.blocks['p1'][1])
    def test_uncertain_page_creation_is_not_repeated(self):
        db.put_item({'PK':'USER#a','SK':'NOTIONMIRROR#w','tasks_creating':True})
        with self.assertRaisesRegex(ValueError,'creation needs review'): mirror.sync('a')
        self.assertEqual(self.pages,{})
        self.assertEqual(db.get_item('USER#a','INTEGRATION#notion')['mirror_status'],'needs_sync')
    def test_pending_append_is_recovered_from_existing_marker(self):
        self.seed(); mirror.sync('a')
        state=db.get_item('USER#a','NOTIONMIRROR#w'); state['pending_appends']={'TASK#t':True}; db.put_item(state)
        mirror.sync('a')
        self.assertEqual(len(self.blocks['p1']),1)
        self.assertEqual(db.get_item('USER#a','NOTIONMIRROR#w')['pending_appends'],{})
    def test_pending_append_missing_does_not_duplicate(self):
        self.seed(); mirror.sync('a'); self.blocks['p1']=[]
        state=db.get_item('USER#a','NOTIONMIRROR#w'); state['pending_appends']={'TASK#t':True}; db.put_item(state)
        with self.assertRaisesRegex(ValueError,'interrupted'): mirror.sync('a')
        self.assertEqual(self.blocks['p1'],[])
    def test_disconnected_does_not_read_or_write_remote(self):
        db.update_item('USER#a','INTEGRATION#notion',{'status':'disconnected'})
        self.assertTrue(mirror.sync('a')['disconnected']); self.assertEqual(self.serial,0)
    def test_habit_log_uses_user_local_date(self):
        from api.routes import habits
        db.put_item({'PK':'USER#a','SK':'HABIT#h','name':'Walk'})
        with patch.object(habits,'today_str',return_value='2026-10-02') as date:
            habits.log_habit({'_path_params':{'id':'h'},'body':'{"completed":true}'},'a')
        date.assert_called_once_with('a')
        self.assertTrue(db.get_item('USER#a','HABITLOG#2026-10-02#h')['completed'])

    def test_owner_isolation(self):
        db.put_item({'PK':'USER#b','SK':'TASK#secret','title':'Other person'})
        mirror.sync('a')
        self.assertEqual(self.blocks['p1'],[])

if __name__=='__main__': unittest.main()
