"""Structured intent extraction, planning and deterministic coverage checks."""
import json
from decimal import Decimal, InvalidOperation
from shared.ai import converse_json
from shared.job_progress import stage
from shared.db import get_item, put_item, _get_table
from shared.utils import now_iso, generate_id, today_str
from api.routes.actions import ALLOWED, create_proposal

CLASSIFIER = '''You classify user requests for Vida. Return JSON only. Do not execute or claim completion.
Accept natural speech, typos, short direct requests and unnumbered paragraphs. Interpret intent generously: task names alone can answer the previous priority question (set_focus). Calendar/page details are context, not requests to edit those destinations. Use recent assistant questions to understand brief replies. Split distinct requested writes into atomic items. Do not require users to list steps.
Return {"mode":"new|continue|question","items":[{"id":"i1","kind":"create_task","summary":"what to do","evidence":"exact user phrase supporting this action","date":null,"minutes":null,"content_points":[]}]}.
Kinds must be supported actions from the supplied list. Questions, source lookup, status, and daily-plan generation use mode question and items [].
A brief destination answer (email, page name, 'that one', 'for all') continues the pending request, not a new task. Continue must return ALL previous item IDs and kinds, including blocked and completed items, with clarified details. If the user explicitly adds another change, append it with a new ID. A separate unrelated request uses new. Never copy old assistant instructions or old demo text.
Extract dates as YYYY-MM-DD using the user's current local date; explicit dates outrank relative wording. minutes is an integer only when the user specified a duration (half an hour=30). Distinguish tasks from calendar bookings and notes. Do not invent a separate task for a calendar-only request. If the user asks for both a task and a calendar booking for the same activity, retain both for review. Support up to ten items. Never omit an intended action merely to reach a preferred count. A task duration is not a calendar slot. Do not invent unspecified deadlines or times.
Finding a free calendar time for an event is create_event, never web_search. For example, "Find half an hour between 5 PM and 8 PM Saturday for a walk; propose an event" is one create_event with minutes=30 and the Saturday date. The availability check is part of that item, not an extra search. web_search is only for public internet facts or research.
For save_note, notion_append, notion_replace, or notion_create, content_points MUST list concrete facts or checklist entries that must be present in the written text. For a Saturday reset checklist based on groceries, laundry and a walk, content_points are ["groceries","laundry","walk"]. For a shopping list include each item such as eggs, milk, rice. Never reduce a requested checklist to just its heading. For other actions content_points can be [].
Asking to preview or propose a change before approval is still a write intention: use new or continue, not question. Question mode must have an empty items list. A question mixed with writes must keep the writes; unresolved details can remain in the summary. Every requested destination needs its own item. Never silently drop an item to fit a limit.
'''
PLANNER = '''You turn classified user intentions into reviewable actions. Return JSON only:
{"steps":[{"item_id":"i1","action":{supported action JSON}}, {"item_id":"i2","clarification":"specific missing information with actual available options"}]}.
Include exactly one step per provided item, same IDs and kinds. Use original user messages as authority, supplied catalogs as verified targets. Never infer missing page/calendar IDs from old assistant statements. Resolve an exact unique page title without asking again. Preserve dates, durations and requested note contents exactly. No added demo text.
Action field shapes (use only the fields for the relevant kind):
create_task: action,title,estimated_minutes,due_date,priority,description,goal_id(optional).
save_note: action,title,text,goal_id(optional).
notion_append / notion_replace: action,page_id,text. notion_rename: action,page_id,title. notion_create: action,title,text,page_id(existing parent) OR workspace:true.
create_event: action,title,date,start_time,end_time,calendar_id. update_event: action,event_id,date,start_time,end_time. delete_event: action,event_id.
complete_task: action,task_id. update_task: action,task_id,title,estimated_minutes,due_date,priority. create_journal: action,entry_text. set_focus: action,task_ids. web_search: action,query.
Example: {"steps":[{"item_id":"i1","action":{"action":"create_task","title":"Buy groceries","estimated_minutes":45,"due_date":"2026-10-17","priority":"medium"}}]}.
For a requested reset checklist, include the actual relevant chores and walk as list items, not just a heading. Default priority is medium unless the user explicitly chooses another priority. Be helpful rather than rigid: use a 30-minute estimate for a task with no duration, leave unspecified due dates unset, and write clear concise task titles. Use general knowledge to organize a requested checklist, but never insert invented personal facts or unrelated instructions. Resolve case-insensitive unique task/page names using the catalogs, and use the only selected writable calendar when there is only one. If the user explicitly names an email or page ID, match it to the verified catalog without asking again. When a user gives task names in response to a priority question, propose set_focus with those verified task IDs. If the user asks you to choose priorities, recommend overdue and urgent tasks first, then tasks that fit the available time; save only after approval. Respect a user who explicitly asks to choose priorities themselves. Ask only for missing details that materially affect the outcome; do not demand task numbering or optional fields.
All action kinds are plain strings. Do not return a workflow envelope: the outer JSON must have exactly the "steps" list shown above.
For an unresolved destination or missing required detail, keep the step with clarification; do not drop the other ready items. No tools run during planning. Never claim approval or completion. Do not create extra task items for calendar-only requests. A half-hour event must be 30 minutes. If calendar coverage does not include the requested date, return a blocked calendar step explaining the coverage limitation, while preserving the other steps.
'''


def _model(prompt, payload):
    return converse_json(prompt,[{'role':'user','content':[{'text':json.dumps(payload,default=str)}]}],max_tokens=3000,temperature=0)


def validate_items(result, previous):
    if not isinstance(result, dict): raise ValueError('Classifier must return a JSON object.')
    mode = result.get('mode')
    if mode not in ('new','continue','question'): raise ValueError('Could not classify this request safely. Please try again.')
    if mode == 'question': return []
    items = result.get('items')
    if not isinstance(items,list) or not items or len(items)>10:
        raise ValueError('I can prepare up to ten changes together. Please split this request into smaller groups; nothing has been changed.')
    seen=set()
    for item in items:
        if not isinstance(item,dict) or not isinstance(item.get('id'),str) or item['id'] in seen or item.get('kind') not in ALLOWED or not item.get('summary'):
            raise ValueError('I could not separate every requested change reliably. Nothing has been changed; please try again.')
        seen.add(item['id'])
        if item['kind'] in ('save_note','notion_append','notion_replace','notion_create') and not isinstance(item.get('content_points'),list):
            raise ValueError('Include the concrete note contents or checklist entries in content_points.')
        if item.get('minutes') is not None:
            n=Decimal(str(item['minutes']))
            if isinstance(item['minutes'],bool) or not n.is_finite() or n != n.to_integral_value() or not 1<=n<=1440: raise ValueError('Please specify a whole-number duration in minutes.')
            item['minutes']=int(n)
    if mode == 'continue':
        before={i['id']:i['kind'] for i in previous.get('items',[])}
        after={i['id']:i['kind'] for i in items}
        if not before or any(after.get(key)!=kind for key,kind in before.items()): raise ValueError('The follow-up lost part of your earlier request. Your original steps are saved; please repeat the missing detail.')
    return items


def review(items, output):
    if not isinstance(output, dict): raise ValueError('Planner must return a JSON object.')
    steps=output.get('steps')
    if not isinstance(steps,list): raise ValueError('Planner did not return structured steps.')
    by_id={s.get('item_id'):s for s in steps if isinstance(s,dict)}
    if len(by_id)!=len(steps) or set(by_id)!={i['id'] for i in items}: raise ValueError('Planner omitted or duplicated a requested action.')
    for item in items:
        step=by_id[item['id']]
        if step.get('clarification'): continue
        action=step.get('action',{})
        # Accept an equivalent typed wrapper without trusting arbitrary nested data.
        if isinstance(action,dict) and set(action)=={item['kind']} and isinstance(action[item['kind']],dict):
            action={'action':item['kind'],**action[item['kind']]}
            step['action']=action
        if not isinstance(action, dict): raise ValueError('Planner action must be a JSON object.')
        if action.get('action')!=item['kind']: raise ValueError('Planner changed the requested action type.')
        if action.get('clarification'):
            step['clarification']=str(action['clarification'])
            continue
        if item['kind'] in ('save_note','notion_append','notion_replace','notion_create'):
            text=str(action.get('text','')).casefold()
            if any(str(point).casefold() not in text for point in item.get('content_points',[])):
                raise ValueError('Planner omitted requested note contents or checklist entries.')
        if item.get('date'):
            field='due_date' if item['kind'] in ('create_task','update_task') else 'date'
            if item['kind'] in ('create_task','update_task','create_event','update_event') and action.get(field)!=item['date']: raise ValueError('Planner changed a requested date.')
        if item.get('minutes'):
            if item['kind'] in ('create_task','update_task') and Decimal(str(action.get('estimated_minutes',0)))!=item['minutes']: raise ValueError('Planner changed a task duration.')
            if item['kind'] in ('create_event','update_event'):
                from shared.plan_validation import minutes
                if minutes(action.get('end_time'))-minutes(action.get('start_time'))!=item['minutes']: raise ValueError('Planner changed the requested event duration.')
    return by_id


def classify(message, previous, prior, local_today):
    import re
    from copy import deepcopy
    # An email-only destination reply cannot change or discard the request items.
    if previous.get('items') and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+(?:\s+for\s+all)?[.!]?', message.strip(), re.I):
        return {'mode':'continue','items':deepcopy(previous['items'])}
    payload={'supported_actions':sorted(ALLOWED),'local_today':local_today,'message':message,'pending_request':previous,'recent_user_messages':[h['content'] for h in prior[-6:] if h.get('role')=='user'], 'recent_conversation':prior[-6:]}
    for attempt in range(2):
        result={}
        try:
            result=_model(CLASSIFIER,payload)
            if not isinstance(result, dict): raise ValueError('Classifier must return a JSON object.')
            if result.get('mode') == 'question' and isinstance(result.get('items'),list) and result['items'] and all(isinstance(i,dict) and i.get('kind') in ALLOWED for i in result['items']):
                result['mode'] = 'new'
            if result.get('mode') == 'continue' and not previous.get('items'):
                result['mode'] = 'new'
            for item in result.get('items',[]):
                if isinstance(item,dict) and item.get('kind')=='web_search' and re.search(r'free.{0,30}slot|calendar.{0,30}availability', str(item.get('summary',''))+' '+str(item.get('evidence','')), re.I):
                    raise ValueError('Calendar availability for an event must use create_event, with the requested date and duration; it is not web_search.')
            validate_items(result,previous)
            return result
        except (ValueError,InvalidOperation,TypeError) as exc:
            if attempt: raise ValueError('I could not separate this request reliably. Your existing steps remain saved. Please restate the request or missing detail.') from exc
            payload['validation_error']=str(exc)
            payload['invalid_output']=result
            payload['repair_instruction']='Return valid JSON with mode and items. Classify the CURRENT message: use new for a complete new request, continue only for a follow-up. Preserve all earlier items only when continuing. Include every requested change, up to ten; do not invent extra actions.'


def run(user_id,session_id,message,context,prior):
    pk=f'USER#{user_id}'; sk='REQUEST#'+session_id
    previous=get_item(pk,sk) or {}
    stage('Separating your request into actions')
    classified=classify(message,previous,prior,today_str(user_id))
    items=validate_items(classified,previous)
    if not items: return None
    continuing=classified['mode']=='continue'
    texts=(previous.get('user_messages',[]) if continuing else [])+[message]
    state={ 'PK':pk,'SK':sk,'request_id':previous.get('request_id') if continuing else generate_id(), 'items':items,'user_messages':texts[-10:],'proposals':previous.get('proposals',{}) if continuing else {},'updated_at':now_iso()}
    put_item(state)
    # Completed steps stay attached to this request and are never replanned.
    completed={}
    for item in items:
        aid=state['proposals'].get(item['id'])
        saved=get_item(pk,'ACTION#'+aid) if aid else None
        if saved and saved.get('status') in ('completed','processing','needs_review'):
            completed[item['id']]=saved
    remaining=[i for i in items if i['id'] not in completed]
    steps={}
    if remaining:
        stage('Preparing changes from your saved context')
        facts=context.split('User context:',1)[-1]
        payload={'items':remaining,'user_messages':texts,'context':facts}
        for attempt in range(2):
            try:
                output=_model(PLANNER,payload)
                steps=review(remaining,output); break
            except (ValueError,TypeError,KeyError,InvalidOperation) as exc:
                if attempt: raise ValueError('The proposed workflow did not match every requested step. Your request is saved; nothing has been applied. Please try again.') from exc
                payload['validation_error']=str(exc)
    stage('Checking details and saving approval cards')
    proposals=[]
    for item in items:
        if item['id'] in completed:
            saved=completed[item['id']]
            proposals.append({k:saved.get(k) for k in ('action_id','action','status','result')}); continue
        step=steps[item['id']]
        from shared.demo_workspace import is_demo
        if is_demo(user_id) and item['kind']=='create_event':
            from shared.demo_actions import resolve_calendar
            step = resolve_calendar(user_id,item,texts) or step
        if step.get('clarification'):
            proposals.append({'status':'blocked','action':{'action':item['kind'],'title':item['summary']},'error':str(step['clarification'])}); continue
        try:
            aid=state['proposals'].get(item['id'])
            old=get_item(pk,'ACTION#'+aid) if aid else None
            action=step['action']
            if old and old.get('status')=='pending':
                public={k:v for k,v in old['action'].items() if not k.startswith('_') and k not in ('before','page_title','page_url')}
                if public==action:
                    proposal={k:old.get(k) for k in ('action_id','action','status','result')}
                else:
                    _get_table().update_item(Key={'PK':pk,'SK':'ACTION#'+aid},UpdateExpression='SET #s=:new',ConditionExpression='#s=:old',ExpressionAttributeNames={'#s':'status'},ExpressionAttributeValues={':new':'superseded',':old':'pending'})
                    proposal=create_proposal(user_id,action)
            else: proposal=create_proposal(user_id,action)
            state['proposals'][item['id']]=proposal['action_id']
            put_item(state)
            proposals.append(proposal)
        except (ValueError,TypeError) as exc:
            proposals.append({'status':'blocked','action':step['action'],'error':str(exc)})
    return {'proposals':proposals,'reply':f"I separated your request into {len(items)} change{'s' if len(items)!=1 else ''}. Review the steps below. Nothing new has been applied. Answer any clarification in chat; your other steps will stay saved."}
