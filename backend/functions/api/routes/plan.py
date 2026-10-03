from shared.db import query_pk, get_item, _get_table, normalize
from shared.utils import response, parse_body, today_str, now_iso, get_query_param


def get_current_plan(event, user_id):
    date = get_query_param(event, "date", today_str(user_id))
    plans = query_pk(f"USER#{user_id}", sk_prefix=f"PLAN#{date}#")

    if not plans:
        return response(200, {"plan": None, "date": date})

    latest = max(plans, key=lambda p: p.get("SK", ""))

    return response(200, {
        "plan": _format_plan(latest),
        "date": date,
    })


def accept_plan(event, user_id):
    body = parse_body(event)
    from shared.demo_workspace import is_demo
    integration = get_item(f"USER#{user_id}", "INTEGRATION#google_calendar") or {}
    if not is_demo(user_id) and (integration.get("status") != "connected" or integration.get("sync_status") != "complete"): raise ValueError("Connect and sync your selected Google calendars before accepting a plan.")
    date = body.get("date", today_str(user_id))
    revision = body.get("revision")

    plans = query_pk(f"USER#{user_id}", sk_prefix=f"PLAN#{date}#")
    if not plans:
        return response(404, {"error": {"code": "NOT_FOUND", "message": "No plans for this date"}})

    if revision is not None:
        rev_str = str(revision).zfill(6)
        target_sk = f"PLAN#{date}#{rev_str}"
        plan = next((p for p in plans if p.get("SK") == target_sk), None)
    else:
        plan = max(plans, key=lambda p: p.get("SK", ""))

    if not plan:
        return response(404, {"error": {"code": "NOT_FOUND", "message": "Plan revision not found"}})

    if plan.get("status") != "draft":
        return response(409, {"error": {"code": "CONFLICT", "message": f"Plan is {plan.get('status')}, not draft"}})

    if plan.get("calendar_signature") != calendar_signature(user_id, date):
        return response(409, {"error":"Your schedule changed. Regenerate the draft before accepting."})

    from shared.models import build_time_block
    from shared.plan_validation import validate
    table = _get_table()
    pk = f"USER#{user_id}"
    existing = [b for b in query_pk(pk, sk_prefix="BLOCK#", limit=10000) if b.get("date") == date]
    blocks = plan.get("blocks", [])
    if not blocks:
        return response(409, {"error": {"message": "This draft has no time blocks to apply. Extend your hours or choose another date and regenerate."}})
    validate(blocks, existing)
    existing_by_id = {b["SK"][6:]:b for b in existing}
    protected = {bid for bid,b in existing_by_id.items() if b.get("locked") or b.get("status") in ("completed", "in_progress") or b.get("source") != "planner"}
    writes = []
    plan.update(status="accepted", accepted_at=now_iso())
    writes.append({"Put":{"TableName":table.name,"Item":normalize(plan),"ConditionExpression":"#s = :draft","ExpressionAttributeNames":{"#s":"status"},"ExpressionAttributeValues":{":draft":"draft"}}})
    for old_plan in plans:
        if old_plan["SK"] != plan["SK"] and old_plan.get("status") == "accepted":
            old_plan['status'] = 'superseded'
            writes.append({"Put":{"TableName":table.name,"Item":normalize(old_plan),"ConditionExpression":"#s = :accepted","ExpressionAttributeNames":{"#s":"status"},"ExpressionAttributeValues":{":accepted":"accepted"}}})
    target_ids = {b.get('block_id') for b in blocks}
    for bid, old in existing_by_id.items():
        if bid in protected:
            writes.append({"ConditionCheck":{"TableName":table.name,"Key":{"PK":pk,"SK":old['SK']},"ConditionExpression":"updated_at = :old","ExpressionAttributeValues":{":old":old['updated_at']}}})
        elif bid not in target_ids:
            writes.append({"Delete":{"TableName":table.name,"Key":{"PK":pk,"SK":old['SK']},"ConditionExpression":"updated_at = :old","ExpressionAttributeValues":{":old":old['updated_at']}}})
    created = 0
    for block in blocks:
        bid = block.get('block_id')
        if bid in protected: continue
        item = build_time_block(user_id, block_id=bid, date=date, start_time=block['start_time'],end_time=block['end_time'],block_type=block.get('block_type','task'),title=block.get('title',''),task_id=block.get('task_id'),source='planner',plan_id=plan.get('plan_id'))
        put={"TableName":table.name,"Item":normalize(item)}
        if bid in existing_by_id:
            put.update(ConditionExpression='updated_at = :old',ExpressionAttributeValues={':old':existing_by_id[bid]['updated_at']})
        else: put['ConditionExpression']='attribute_not_exists(PK)'
        writes.append({'Put':put}); created+=1
    if len(writes)>100: raise ValueError('Too many schedule changes for one plan. Reduce the plan size.')
    try:
        table.meta.client.transact_write_items(TransactItems=writes)
    except table.meta.client.exceptions.TransactionCanceledException:
        return response(409, {'error':{'message':'Your schedule changed. Refresh and regenerate the plan.'}})
    return response(200, {'plan':_format_plan(plan), 'blocks_created':created})


def _format_plan(item):
    sk = item.get("SK", "")
    parts = sk.split("#")
    return {
        "date": item.get("date"),
        "revision": item.get("revision", 0),
        "plan_id": item.get("plan_id"),
        "status": item.get("status", "draft"),
        "total_available_minutes": item.get("total_available_minutes", 0),
        "total_planned_minutes": item.get("total_planned_minutes", 0),
        "total_break_minutes": item.get("total_break_minutes", 0),
        "total_buffer_minutes": item.get("total_buffer_minutes", 0),
        "blocks": item.get("blocks", []),
        "deferred_tasks": item.get("deferred_tasks", []),
        "assumptions": item.get("assumptions", []),
        "explanation": item.get("explanation", ""),
        "changes_from_previous": item.get("changes_from_previous", []),
        "reviewer_objections": item.get("reviewer_objections", []),
        "accepted_at": item.get("accepted_at"),
        "created_at": item.get("created_at"),
    }


def calendar_signature(user_id, date):
    import hashlib, json
    rows = [b for b in query_pk(f'USER#{user_id}', 'BLOCK#', limit=10000) if b.get('date') == date]
    return hashlib.sha256(json.dumps(sorted((b['SK'], b.get('updated_at','')) for b in rows)).encode()).hexdigest()


def planning_context(user_id, date):
    from datetime import date as Date, timedelta
    from shared.agents import _get_user_context
    from shared.plan_validation import minutes
    Date.fromisoformat(date)
    ctx = _get_user_context(user_id, date=date)
    integration = get_item(f'USER#{user_id}', 'INTEGRATION#google_calendar') or {}
    connected = integration.get('status') == 'connected'
    blockers = []
    from shared.demo_workspace import is_demo
    demo = is_demo(user_id)
    if demo: pass
    elif not connected: blockers.append('Connect Google Calendar in Settings before planning.')
    elif not integration.get('selected_calendars'): blockers.append('Choose your calendars in Settings.')
    elif not integration.get('last_synced_at') or integration.get('sync_status') != 'complete': blockers.append('Sync your selected calendars before planning.')
    first = Date.fromisoformat(today_str(user_id))
    if not first <= Date.fromisoformat(date) < first + timedelta(days=7): blockers.append('Choose a date within the next 7 days covered by calendar sync.')
    active_ids = {t['task_id'] for t in ctx['tasks']}
    focus = [tid for tid in ctx['profile']['planning_focus_task_ids'] if tid in active_ids]
    if not focus: blockers.append('Choose the tasks you want to prioritize before generating a plan.')
    start, end = ctx['profile']['day_start'], ctx['profile']['day_end']
    from datetime import datetime
    from zoneinfo import ZoneInfo
    if date == today_str(user_id):
        now = datetime.now(ZoneInfo(ctx['profile']['timezone'] or 'UTC'))
        start = max(start, now.strftime('%H:%M'))
    occupied = set()
    for block in ctx.get('existing_blocks', []):
        if block.get('locked') or block.get('source') != 'planner' or block.get('status') in ('completed','in_progress'):
            occupied.update(range(max(minutes(start),minutes(block['start_time'])), min(minutes(end),minutes(block['end_time']))))
    available = max(0, minutes(end)-minutes(start)-len(occupied))
    warnings = ['Sample schedule only — not Google Calendar. Start a clean personal workspace for real integrations.'] if demo else []
    if not available: warnings.append('No free time remains within your preferred hours. You can still generate a draft to review unscheduled tasks, extend your hours, or plan another day.')
    return {**ctx, 'date':date,'google_connected':connected,'selected_calendars':integration.get('selected_calendars',[]),
        'last_synced_at':integration.get('last_synced_at'),'blockers':blockers, 'focus_task_ids':focus,
        'day_start':start,'day_end':end,'available_minutes':available,'warnings':warnings}


def get_context(event, user_id):
    return response(200, planning_context(user_id, get_query_param(event,'date',today_str(user_id))))
