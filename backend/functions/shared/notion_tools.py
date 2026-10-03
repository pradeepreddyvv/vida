"""Scoped Notion edits with live previews and stale-content checks."""
import hashlib
import json
import re
import time
from shared.db import get_item, put_item
from shared.utils import now_iso

TEXT_TYPES = {'paragraph','heading_1','heading_2','heading_3','bulleted_list_item','numbered_list_item','quote','to_do','callout'}

def _headers(user_id):
    conn = get_item(f'USER#{user_id}', 'INTEGRATION#notion') or {}
    if conn.get('status') != 'connected': raise ValueError('Connect Notion and sync the pages you want Vida to edit.')
    return {'Authorization':'Bearer '+conn['access_token'], 'Notion-Version':'2022-06-28','Content-Type':'application/json'}

def _request(user_id, path, data=None, method='GET'):
    from api.routes.integrations import _http_request
    return _http_request('https://api.notion.com/v1/'+path, data=data, headers=_headers(user_id), method=method)

def snapshot(user_id, page_id):
    if not isinstance(page_id,str) or not re.fullmatch(r'[a-fA-F0-9-]{32,36}',page_id): raise ValueError('Choose a Notion page from your synced Library.')
    doc=get_item(f'USER#{user_id}', 'DOC#notion-'+page_id)
    if not doc or doc.get('source') != 'notion': raise ValueError('That Notion page is not in your synced workspace. Share and sync it first.')
    page=_request(user_id,'pages/'+page_id)
    if page.get('archived') or page.get('in_trash'): raise ValueError('This Notion page is archived.')
    children=_request(user_id,'blocks/'+page_id+'/children?page_size=100')
    blocks=children.get('results',[])
    text='\n'.join(''.join(t.get('plain_text', t.get('text',{}).get('content','')) for t in b.get(b.get('type',''),{}).get('rich_text',[])) for b in blocks)
    signature=hashlib.sha256(json.dumps({'edited':page.get('last_edited_time'),'blocks':blocks},sort_keys=True).encode()).hexdigest()
    return {'page_id':page_id,'title':doc.get('file_name','Notion page'),'url':page.get('url') or 'https://www.notion.so/'+page_id.replace('-',''), 'text':text,'signature':signature,'blocks':blocks,'has_more':children.get('has_more',False), 'title_property':next((k for k,v in page.get('properties',{}).items() if v.get('type')=='title'),'title')}

def prepare(user_id, action):
    kind=action['action']
    workspace = kind == 'notion_create' and action.get('workspace') is True and not action.get('page_id')
    if workspace:
        _headers(user_id)
        snap={'title':'your private Notion workspace','url':'','text':'','signature':'workspace-create'}
    else:
        snap=snapshot(user_id,action.get('page_id'))
    text=action.get('text','')
    if kind in ('notion_append','notion_replace','notion_create') and (not isinstance(text,str) or not text.strip() or len(text)>10000): raise ValueError('Provide between 1 and 10,000 characters for the Notion edit.')
    if kind=='notion_replace' and (snap['has_more'] or len(snap['text'])>16000 or len(snap['blocks'])>10 or any(b.get('type') not in TEXT_TYPES or b.get('has_children') for b in snap['blocks'])):
        raise ValueError('Whole-page replacement supports small text-only pages (up to 10 blocks). This page has richer content; ask me to append instead so its layout and subpages stay intact.')
    if kind in ('notion_rename','notion_create') and (not isinstance(action.get('title'),str) or not 1<=len(action['title'].strip())<=200): raise ValueError('Provide a page title of up to 200 characters.')
    return {k:action[k] for k in ('action','page_id','workspace','text','title') if k in action} | {'page_title':snap['title'],'page_url':snap['url'],'before':snap['text'][:16000], '_signature':snap['signature']}

def _paragraphs(text):
    return [{'object':'block','type':'paragraph','paragraph':{'rich_text':[{'type':'text','text':{'content':text[i:i+1800]}}]}} for i in range(0,len(text),1800)]

def execute(user_id, action):
    workspace = action['action'] == 'notion_create' and action.get('workspace') is True and not action.get('page_id')
    if workspace:
        _headers(user_id)
        snap={'signature':'workspace-create','title':'your private Notion workspace','url':''}
    else:
        snap=snapshot(user_id, action['page_id'])
    if snap['signature'] != action['_signature']: raise ValueError('The Notion page changed since the preview. Ask Vida for a fresh preview.')
    kind=action['action']; pid=action.get('page_id'); url=snap['url']
    doc=get_item(f'USER#{user_id}', 'DOC#notion-'+pid) if pid else None
    if doc:
        doc.update(kb_status='pending',updated_at=now_iso()); put_item(doc)
    if kind=='notion_rename':
        _request(user_id,'pages/'+pid, {'properties':{snap['title_property']:{'type':'title','title':[{'type':'text','text':{'content':action['title']}}]}}},'PATCH')
    elif kind=='notion_create':
        created=_request(user_id,'pages',{'parent':{'workspace':True} if workspace else {'page_id':pid},'properties':{'title':{'type':'title','title':[{'type':'text','text':{'content':action['title']}}]}},'children':_paragraphs(action['text'])},'POST')
        pid=created['id'];url=created.get('url',url)
    else:
        _request(user_id,'blocks/'+pid+'/children',{'children':_paragraphs(action['text'])},'PATCH')
        if kind=='notion_replace':
            for block in snap['blocks']:
                time.sleep(.35)
                _request(user_id,'blocks/'+block['id'],{'archived':True},'PATCH')
    # Refresh simple text pages immediately; nested content stays excluded until sync.
    from shared.models import build_document
    note = ''
    try:
        current = _request(user_id, 'blocks/'+pid+'/children?page_size=100')
        children = current.get('results', [])
        if current.get('has_more') or any(b.get('has_children') for b in children):
            note = ' Sync Notion to refresh nested content before asking questions about it.'
        else:
            text = '\n'.join(''.join(t.get('plain_text',t.get('text',{}).get('content','')) for t in b.get(b.get('type',''),{}).get('rich_text',[])) for b in children)
            if len(text.encode('utf-8')) > 200000: raise ValueError('Page too large to index')
            doc = build_document(user_id, doc_id='notion-'+pid, file_name=action.get('title') if kind in ('notion_create','notion_rename') else snap['title'], file_type='md', extracted_text=text, kb_status='indexed')
            doc.update(source='notion', notion_id=pid)
            put_item(doc)
    except Exception:
        note = ' The edit succeeded, but searchable content needs a Notion sync.'
    return {'message':{'notion_append':'Appended text to','notion_replace':'Replaced the text of','notion_rename':'Renamed','notion_create':'Created a page under'}[kind]+' '+snap['title']+'.'+note, 'url':url, 'page_id':pid, 'destination':'Notion'}
