"""Seed fictional demo content into a newly generated, owner-isolated workspace."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from shared.db import put_item
from shared.models import build_profile, build_goal, build_task, build_habit, build_document, build_time_block

PERSONAS = {
    'everyday': ('Sam', 'Everyday organizer', 'Saturday reset', [('Plan weekly meals',30), ('Sort household paperwork',20), ('Review the weekly budget',25)]),
    'student': ('Maya', 'Student', 'Study week', [('Review sorting algorithms',45), ('Outline the group presentation',30), ('Practice interview questions',25)]),
    'builder': ('Alex', 'Software builder', 'Product launch', [('Review the onboarding flow',30), ('Write release notes',20), ('Prepare the product walkthrough',45)]),
}

def seed(user_id, persona, timezone):
    if persona not in PERSONAS: raise ValueError('Choose a listed demo profile.')
    try: zone = ZoneInfo(timezone)
    except (ValueError, KeyError, TypeError): raise ValueError('Choose a valid timezone.')
    name, role, project, task_specs = PERSONAS[persona]
    tomorrow = (datetime.now(zone).date()+timedelta(days=1)).isoformat()
    profile = build_profile(user_id, name=name+' (sample)', role=role, timezone=timezone,
        onboarded=True, summary='Fictional sample profile for exploring Vida.', day_start='09:00', day_end='20:00')
    profile.update(demo_profile=persona, sample_data=True)
    goal = build_goal(user_id,title=project,description='Sample project: edit these tasks to explore your own workflow.',target_date=tomorrow,source='demo')
    put_item(goal)
    focus=[]
    for title, duration in task_specs:
        task=build_task(user_id,title=title,estimated_minutes=duration,due_date=tomorrow,goal_id=goal['SK'][5:],source='demo',description='Fictional demo task. Edit or complete it freely.')
        put_item(task); focus.append(task['SK'][5:])
    for name in ['Drink water','Read for 15 minutes','Take a short walk']:
        put_item(build_habit(user_id,name=name,frequency='daily',source='demo',reason='Sample habit; customize to suit you.'))
    for title,text in [('Sample shopping list','Sample groceries: eggs, milk, rice, spinach, and bananas.'),
                       ('Sample project notes',f'{project}: choose one important outcome, split work into short tasks, and leave room for breaks. This is fictional sample content, not a fact about you.'),
                       ('How to try Vida','This is an isolated sample workspace. Start a clean personal workspace before connecting Google Calendar or Notion. Use Show my sources to retrieve sample notes. Select tasks in Plan and generate a draft. Changes need approval. No sample data is transferred to a personal workspace.')]:
        doc=build_document(user_id,file_name=title,extracted_text=text,kb_status='indexed')
        doc.update(source='note',sample_data=True,goal_id=goal['SK'][5:]);put_item(doc)
    for offset in range(7):
        date=(datetime.now(zone).date()+timedelta(days=offset)).isoformat()
        put_item(build_time_block(user_id,date=date,title='Sample commitment — morning meeting',start_time='10:00',end_time='11:00',source='demo',locked=True))
        put_item(build_time_block(user_id,date=date,title='Sample commitment — lunch',start_time='12:00',end_time='13:00',source='demo',locked=True))
    profile['planning_focus_task_ids']=focus[:2]
    put_item(profile)
    return profile


def is_demo(user_id):
    from shared.db import get_item
    return bool((get_item(f'USER#{user_id}','PROFILE') or {}).get('sample_data'))

def require_personal(user_id):
    if is_demo(user_id):
        raise ValueError('Test workspaces cannot connect or sync personal accounts. Choose Start clean & connect my accounts; no sample data will be carried over.')


def sample_plan(tasks, existing, start, end):
    """Honest, deterministic fallback for an invalid AI draft in test mode only."""
    from shared.plan_validation import minutes
    from shared.utils import generate_id
    occupied=set()
    for block in existing:
        if block.get('locked') or block.get('source')!='planner' or block.get('status') in ('completed','in_progress'):
            occupied.update(range(minutes(block['start_time']),minutes(block['end_time'])))
    blocks=[]
    for task in tasks:
        duration=int(task.get('remaining_minutes') or task.get('estimated_minutes') or 30)
        if not 1<=duration<=1440: continue
        for begin in range(minutes(start),minutes(end)-duration+1):
            slot=range(begin,begin+duration)
            if not any(m in occupied for m in slot):
                finish=begin+duration
                blocks.append({'block_id':generate_id(),'block_type':'task','task_id':task['task_id'],'title':task['title'],
                               'start_time':f'{begin//60:02d}:{begin%60:02d}','end_time':f'{finish//60:02d}:{finish%60:02d}'})
                occupied.update(slot)
                break
    return {'blocks':blocks,'explanation':'The AI draft did not pass schedule validation. This sample draft uses scheduling rules to fit selected tasks around the sample commitments. Review before accepting. No Google Calendar events are created.', 'assumptions':['Sample schedule, not a connected Google Calendar.']}
