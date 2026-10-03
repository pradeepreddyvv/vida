"""Local sample destinations. Never calls Google or Notion."""
import re
from datetime import date
from shared.db import get_item, put_item, query_pk, _get_table
from shared.models import build_document, build_time_block
from shared.demo_workspace import is_demo
from shared.plan_validation import minutes, validate
from shared.utils import now_iso

PAGE='demo-notion'
CALENDAR='demo-calendar'

def page(user_id):
    if not is_demo(user_id): raise ValueError('Sample destinations require a test workspace.')
    key={'PK':f'USER#{user_id}','SK':'DOC#'+PAGE}
    found=get_item(key['PK'],key['SK'])
    if found: return found
    item=build_document(user_id,doc_id=PAGE,file_name='Vida demo test',extracted_text='This is a sample Notion page stored only inside Vida. It is not synced to Notion.',kb_status='indexed')
    item.update(source='note',sample_data=True,demo_page=True)
    table=_get_table()
    try: table.put_item(Item=item,ConditionExpression='attribute_not_exists(PK)')
    except table.meta.client.exceptions.ConditionalCheckFailedException: pass
    return get_item(key['PK'],key['SK'])

def prepare(user_id, action):
    if not is_demo(user_id): raise ValueError('Sample destinations require a test workspace.')
    action=dict(action)
    kind=action['action']
    if kind=='notion_append':
        doc=page(user_id)
        if action.get('page_id') not in (None,PAGE): raise ValueError('Choose the sample page Vida demo test; real Notion pages are not available in test mode.')
        if not isinstance(action.get('text'),str) or not 1<=len(action['text'])<=20000: raise ValueError('Provide the text to append.')
        action.update(page_id=PAGE,page_title='Vida demo test (sample)',before=doc['extracted_text'],_before=doc['extracted_text'])
    elif kind=='create_event':
        if action.get('calendar_id') not in (None,CALENDAR): raise ValueError('Choose the sample calendar; real calendars are not available in test mode.')
        date.fromisoformat(action.get('date',''))
        if not action.get('title'): raise ValueError('Give the sample event a title.')
        existing=[b for b in query_pk(f'USER#{user_id}','BLOCK#',limit=10000) if b.get('date')==action['date']]
        validate([action],existing)
        action['calendar_id']=CALENDAR
    else: raise ValueError('This sample supports appending to the sample Notion page and adding sample calendar events. Start clean for other real integration actions.')
    action.update(_demo=True,destination_mode='Demo only — not synced')
    return action

def mutation(user_id, action, action_id):
    if not is_demo(user_id): raise ValueError('Sample action cannot run in a personal workspace.')
    if action['action']=='notion_append':
        current=page(user_id)
        if current['extracted_text']!=action['_before']: raise ValueError('The sample page changed. Ask for a fresh preview before appending.')
        item={**current,'extracted_text':current['extracted_text']+'\n\n'+action['text'],'updated_at':now_iso()}
        return item, {'message':'Appended to Vida demo test. Completed in demo only—not synced to Notion.','url':'/library','demo':True}
    prepare(user_id,action) # Recheck collisions immediately before committing locally.
    item=build_time_block(user_id,block_id='demo-'+action_id,date=action['date'],title=action['title']+' (demo only)',start_time=action['start_time'],end_time=action['end_time'],source='demo_calendar',locked=True)
    return item, {'message':'Calendar event completed in demo only—not synced to Google Calendar.','url':'/plan?date='+action['date'],'demo':True}

def resolve_calendar(user_id,item,texts):
    """Resolve a requested time window against local sample commitments."""
    text='\n'.join(texts)
    match=re.search(r'between\s+(\d{1,2})(?::(\d{2}))?\s*(AM|PM)\s+and\s+(\d{1,2})(?::(\d{2}))?\s*(AM|PM)',text,re.I)
    if not match or not item.get('date') or not item.get('minutes'): return None
    def clock(h,m,period): return (int(h)%12+(12 if period.upper()=='PM' else 0))*60+int(m or 0)
    start=clock(*match.groups()[:3]);end=clock(*match.groups()[3:])
    if any(not 1 <= int(h) <= 12 or not 0 <= int(m or 0) <= 59 for h,m,_ in (match.groups()[:3],match.groups()[3:])): return None
    date.fromisoformat(item['date'])
    duration=int(item['minutes'])
    if not 1 <= duration <= 1440 or end <= start: return None
    existing=[b for b in query_pk(f'USER#{user_id}','BLOCK#',limit=10000) if b.get('date')==item['date']]
    title=re.search(r'event (?:titled|called)\s+[“"]([^”"]+)',text,re.I)
    for begin in range(start,end-duration+1):
        action={'action':'create_event','calendar_id':CALENDAR,'title':title.group(1) if title else 'Sample focus time','date':item['date'],'start_time':f'{begin//60:02d}:{begin%60:02d}','end_time':f'{(begin+duration)//60:02d}:{(begin+duration)%60:02d}'}
        try: validate([action],existing)
        except ValueError: continue
        return {'item_id':item['id'],'action':action}
    return {'item_id':item['id'],'clarification':'No free slot fits in the sample calendar during that window. What other time window should I check?'}
