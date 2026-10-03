"""One-way Vida task/habit mirrors. Only blocks owned by this mirror are edited."""
import json
import logging
import os
import time
from urllib.parse import quote
from shared.db import get_item, put_item, query_pk, update_item
from shared.utils import now_iso
from shared.notion_tools import _request
from api.routes.integrations import _serialized_sync

logger = logging.getLogger(__name__)
BASE = 'https://dahb851px2bik.cloudfront.net'


def request_sync(user_id):
    from shared.demo_workspace import is_demo
    if is_demo(user_id): return {'status':'disabled_in_demo'}
    """Queue after a successful local write; remote failure must not undo that write."""
    conn = get_item(f'USER#{user_id}', 'INTEGRATION#notion') or {}
    if conn.get('status') != 'connected':
        return
    try:
        update_item(f'USER#{user_id}', 'INTEGRATION#notion', {'mirror_status':'pending'})
        import boto3
        from botocore.config import Config
        client = boto3.client('lambda', config=Config(connect_timeout=3, read_timeout=5, retries={'total_max_attempts':2}))
        client.invoke(FunctionName=os.environ.get('AI_FUNCTION_NAME','vida-ai'), InvocationType='Event',
                      Payload=json.dumps({'operation':'notion_mirror','user_id':user_id}))
    except Exception:
        logger.exception('Could not queue Notion mirror')
        update_item(f'USER#{user_id}', 'INTEGRATION#notion', {'mirror_status':'needs_sync','mirror_error':'Saved in Vida. Open Settings and sync Notion to retry.'})


def _text(content, link=None):
    text = {'content':content}
    if link: text['link'] = {'url':link}
    return {'type':'text','text':text}


def _children(uid, page):
    rows, cursor = [], None
    for _ in range(30):
        path = f'blocks/{page}/children?page_size=100'
        if cursor: path += '&start_cursor='+quote(cursor)
        data = _request(uid,path)
        rows.extend(data.get('results',[]))
        if not data.get('has_more'): return rows
        cursor = data['next_cursor']
    raise ValueError('This page is too large to sync safely. Your existing content was preserved.')


def _rows(uid):
    pk = f'USER#{uid}'
    tasks = query_pk(pk,'TASK#',limit=1001,consistent=True)
    habits = query_pk(pk,'HABIT#',limit=1001,consistent=True)
    logs = query_pk(pk,'HABITLOG#',limit=1001,consistent=True)
    if max(len(tasks),len(habits),len(logs)) > 1000:
        raise ValueError('Notion mirror currently supports up to 1,000 tasks, habits, or check-ins per workspace.')
    desired = {'tasks':{}, 'habits':{}}
    for t in tasks:
        label = f"{t.get('title','Task')} — {t.get('status','todo')} · {t.get('estimated_minutes',30)} min · {t.get('priority','medium')} priority"
        if t.get('due_date'): label += ' · Due '+t['due_date']
        if t.get('description'): label += '\n'+t['description']
        desired['tasks'][t['SK']] = (label, t.get('status') == 'done')
    names = {h['SK'][6:]:h.get('name','Habit') for h in habits}
    for h in habits:
        label = f"{h.get('name','Habit')} — {h.get('frequency','daily')}"
        if h.get('reason'): label += '\n'+h['reason']
        desired['habits'][h['SK']] = (label, None)
    for log in logs:
        _, date, hid = log['SK'].split('#',2)
        if hid in names:
            desired['habits'][log['SK']] = (f"{date} · {names[hid]}",bool(log.get('completed')))
    return desired


def _ensure_page(uid, state, kind):
    if state.get(kind+'_id'): return state[kind+'_id']
    # An uncertain POST is never blindly repeated: it may already have created a page.
    if state.get(kind+'_creating'):
        raise ValueError('Notion page creation needs review after an interrupted request. Do not reconnect to retry; contact support to recover the existing page link.')
    state[kind+'_creating'] = True
    put_item(state)
    title = 'Vida Tasks' if kind == 'tasks' else 'Vida Habits'
    data = _request(uid,'pages',{'parent':{'workspace':True},'properties':{'title':{'type':'title','title':[_text(title)]}},
        'children':[{'object':'block','type':'paragraph','paragraph':{'rich_text':[_text('Synced from Vida. Make task and habit changes in Vida; they appear here automatically. Your own notes outside the managed items are preserved.')]}}]},'POST')
    state[kind+'_id'] = data['id']
    state[kind+'_url'] = data.get('url') or 'https://www.notion.so/'+data['id'].replace('-','')
    state[kind+'_creating'] = False
    put_item(state)
    return data['id']


def _sync_page(uid, state, kind, desired, deadline):
    page = _ensure_page(uid,state,kind)
    info = _request(uid,'pages/'+page)
    if info.get('archived') or info.get('in_trash'):
        raise ValueError('Restore your Vida '+kind+' page in Notion, then sync again. No replacement page was created.')
    prefix = BASE+'/projects#vida-sync-'+uid+'-'
    existing = {}
    for block in _children(uid,page):
        for rt in block.get(block.get('type',''),{}).get('rich_text',[]):
            url = rt.get('href') or (rt.get('text',{}).get('link') or {}).get('url','')
            if url.startswith(prefix):
                key = url[len(prefix):]
                if key in existing: raise ValueError('Duplicate managed Notion items found. Resolve them before syncing.')
                existing[key] = block
    for key, (label, checked) in desired.items():
        if time.monotonic() > deadline: raise TimeoutError('Sync is continuing. If it stays pending, use Sync in Settings.')
        kind_key = quote(key,safe='')
        block = existing.get(kind_key)
        block_type = 'paragraph' if checked is None else 'to_do'
        value = {'rich_text':[_text(label[:1800]),_text(' · Open in Vida',prefix+kind_key)]}
        if checked is not None: value['checked'] = checked
        if block:
            old = block.get(block_type,{})
            old_text = [(t.get('plain_text',t.get('text',{}).get('content','')), t.get('href') or (t.get('text',{}).get('link') or {}).get('url')) for t in old.get('rich_text',[])]
            new_text = [(t['text']['content'],(t['text'].get('link') or {}).get('url')) for t in value['rich_text']]
            if old_text != new_text or old.get('checked') != value.get('checked'):
                _request(uid,'blocks/'+block['id'],{block_type:value},'PATCH')
                time.sleep(.35)
        else:
            pending = state.setdefault('pending_appends', {})
            if pending.get(key):
                raise ValueError('A Notion item write was interrupted. Sync again after checking the page; Vida will not create a duplicate.')
            state['pending_appends'][key] = True
            put_item(state)
            _request(uid,f'blocks/{page}/children',{'children':[{'object':'block','type':block_type,block_type:value}]},'PATCH')
            state['pending_appends'].pop(key, None)
            put_item(state)
            time.sleep(.35)
        if state.get('pending_appends', {}).get(key):
            state['pending_appends'].pop(key, None)
            put_item(state)
    # Soft-archive only mirror-owned rows removed in Vida; preserve all manual notes.
    desired_keys = {quote(k,safe='') for k in desired}
    for key, block in existing.items():
        if key not in desired_keys:
            if time.monotonic() > deadline: raise TimeoutError('More items remain. Sync again to continue.')
            _request(uid,'blocks/'+block['id'],{'archived':True},'PATCH')
            time.sleep(.35)


@_serialized_sync('notion_mirror')
def sync(user_id):
    from shared.demo_workspace import is_demo
    if is_demo(user_id): return {'status':'disabled_in_demo'}
    pk = f'USER#{user_id}'
    conn = get_item(pk,'INTEGRATION#notion') or {}
    if conn.get('status') != 'connected': return {'disconnected':True}
    workspace = conn.get('workspace_id')
    if not workspace: raise ValueError('Reconnect Notion to identify your workspace.')
    state = get_item(pk,'NOTIONMIRROR#'+workspace) or {'PK':pk,'SK':'NOTIONMIRROR#'+workspace}
    try:
        update_item(pk,'INTEGRATION#notion',{'mirror_status':'syncing','mirror_error':None})
        rows = _rows(user_id)
        deadline = time.monotonic()+30
        for kind in ('tasks','habits'):
            _sync_page(user_id,state,kind,rows[kind],deadline)
        if _rows(user_id) != rows:
            raise TimeoutError('Tasks or habits changed during sync. Another pass is needed to include the latest changes.')
        urls = {kind:state[kind+'_url'] for kind in ('tasks','habits')}
        update_item(pk,'INTEGRATION#notion',{'mirror_status':'complete','mirror_error':None,'mirror_synced_at':now_iso(),'mirror_pages':urls})
        return {'pages':urls,'tasks':len(rows['tasks']),'habits_and_checkins':len(rows['habits'])}
    except Exception as exc:
        update_item(pk,'INTEGRATION#notion',{'mirror_status':'needs_sync','mirror_error':str(exc)[:400]})
        raise
