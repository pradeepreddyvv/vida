import json
import logging
import os
import boto3
from shared.db import query_pk, query_gsi, get_item, put_item, batch_write
from shared.models import (
    build_chat_message, build_daily_plan, build_daily_report,
    build_time_block, build_goal, build_task, build_habit, build_document,
)
from shared.utils import generate_id, now_iso, today_str
from shared.ai import converse, converse_json, chat_turn, retrieve_from_kb
from shared import prompts

logger = logging.getLogger(__name__)


def _get_user_context(user_id, include_calendar=True):
    profile = get_item(f"USER#{user_id}", "PROFILE") or {}
    goals = query_gsi("GSI1", f"USER#{user_id}", sk_prefix="GOALSTATUS#active#")
    tasks_todo = query_gsi("GSI1", f"USER#{user_id}", sk_prefix="TASKSTATUS#todo#")
    tasks_ip = query_gsi("GSI1", f"USER#{user_id}", sk_prefix="TASKSTATUS#in_progress#")
    habits = query_pk(f"USER#{user_id}", sk_prefix="HABIT#")

    ctx = {
        "profile": {
            "name": profile.get("name", ""),
            "role": profile.get("role", ""),
            "planning_mode": profile.get("planning_mode", "balanced"),
            "availability": profile.get("availability", {}),
            "timezone": profile.get("timezone", "America/Los_Angeles"),
        },
        "goals": [{"goal_id": g["SK"].replace("GOAL#", ""), "title": g.get("title"), "status": g.get("status")} for g in goals if g.get("SK", "").startswith("GOAL#")],
        "tasks": [],
        "habits": [{"name": h.get("name"), "frequency": h.get("frequency")} for h in habits if h.get("SK", "").startswith("HABIT#")],
    }

    for t in tasks_todo + tasks_ip:
        if not t.get("SK", "").startswith("TASK#"):
            continue
        ctx["tasks"].append({
            "task_id": t["SK"].replace("TASK#", ""),
            "title": t.get("title"),
            "due_date": t.get("due_date"),
            "priority": t.get("priority", "medium"),
            "status": t.get("status"),
            "estimated_minutes": t.get("estimated_minutes", 30),
            "energy": t.get("energy", "any"),
            "splittable": t.get("splittable", False),
            "min_block_minutes": t.get("min_block_minutes", 15),
            "goal_id": t.get("goal_id"),
        })

    if include_calendar:
        date = today_str()
        blocks = query_gsi("GSI2", f"USER#{user_id}", sk_prefix=f"DATE#{date}#BLOCK")
        ctx["existing_blocks"] = [{
            "block_id": b["SK"].replace("BLOCK#", ""),
            "start_time": b.get("start_time"),
            "end_time": b.get("end_time"),
            "title": b.get("title"),
            "block_type": b.get("block_type"),
            "locked": b.get("locked", False),
            "status": b.get("status", "scheduled"),
            "task_id": b.get("task_id"),
        } for b in blocks if b.get("SK", "").startswith("BLOCK#")]

    return ctx


# --- Chat ---

def process_chat(user_id, job_input):
    message = job_input.get("message", "")
    session_id = job_input.get("session_id", "default")

    put_item(build_chat_message(user_id, session_id, "user", message))

    ctx = _get_user_context(user_id, include_calendar=True)

    rag_context = ""
    rag_results = retrieve_from_kb(message)
    if rag_results:
        rag_context = "\n\nRelevant context from your documents:\n"
        for r in rag_results[:3]:
            rag_context += f"- {r['text'][:500]}\n"

    system = prompts.CHAT_SYSTEM + f"""

User context:
- Name: {ctx['profile']['name']}
- Role: {ctx['profile']['role']}
- Active goals: {json.dumps([g['title'] for g in ctx['goals']])}
- Pending tasks: {len(ctx['tasks'])} tasks
- Today's blocks: {len(ctx.get('existing_blocks', []))} scheduled
{rag_context}"""

    history = query_pk(f"USER#{user_id}", sk_prefix=f"CHAT#{session_id}#", limit=20, scan_forward=False)
    history.reverse()
    chat_history = [{"role": h.get("role"), "content": h.get("content")} for h in history if h.get("role") in ("user", "assistant")]

    reply = chat_turn(system, message, history=chat_history[:-1] if chat_history else None, max_tokens=1024)

    put_item(build_chat_message(user_id, session_id, "assistant", reply, agent="chat"))

    return {"reply": reply, "session_id": session_id}


# --- Plan Generate ---

def process_plan_generate(user_id, job_input):
    date = job_input.get("date", today_str())
    ctx = _get_user_context(user_id)

    existing_plans = query_pk(f"USER#{user_id}", sk_prefix=f"PLAN#{date}#")
    revision = len(existing_plans)

    planner_input = json.dumps({
        "date": date,
        "availability": ctx["profile"]["availability"],
        "planning_mode": ctx["profile"]["planning_mode"],
        "existing_blocks": ctx.get("existing_blocks", []),
        "tasks": ctx["tasks"],
        "goals": ctx["goals"],
        "habits": ctx["habits"],
    }, default=str)

    messages = [{"role": "user", "content": [{"text": f"Create a daily plan for {date}.\n\nContext:\n{planner_input}"}]}]
    plan_result = converse_json(prompts.PLANNER_SYSTEM, messages, max_tokens=4096, temperature=0.3)

    reviewer_input = json.dumps({
        "proposed_plan": plan_result,
        "availability": ctx["profile"]["availability"],
        "existing_locked_blocks": [b for b in ctx.get("existing_blocks", []) if b.get("locked")],
    }, default=str)

    review_messages = [{"role": "user", "content": [{"text": f"Review this proposed plan:\n\n{reviewer_input}"}]}]
    review_result = converse_json(prompts.REVIEWER_SYSTEM, review_messages, max_tokens=2048, temperature=0.2)

    if not review_result.get("approved") and review_result.get("repair"):
        plan_result = review_result["repair"]
    elif not review_result.get("approved") and review_result.get("objections"):
        critical = [o for o in review_result["objections"] if o.get("severity") == "critical"]
        if critical:
            repair_prompt = f"The reviewer found critical issues. Fix them:\n{json.dumps(critical)}\n\nOriginal plan:\n{json.dumps(plan_result)}"
            repair_messages = [{"role": "user", "content": [{"text": repair_prompt}]}]
            plan_result = converse_json(prompts.PLANNER_SYSTEM, repair_messages, max_tokens=4096, temperature=0.3)

    validation = _validate_plan(plan_result, ctx)

    blocks = plan_result.get("blocks", [])
    for b in blocks:
        if not b.get("block_id"):
            b["block_id"] = generate_id()

    total_planned = sum(_block_duration(b) for b in blocks if b.get("block_type") == "task")
    total_break = sum(_block_duration(b) for b in blocks if b.get("block_type") == "break")
    total_buffer = sum(_block_duration(b) for b in blocks if b.get("block_type") == "buffer")

    plan_item = build_daily_plan(
        user_id, date, revision=revision,
        status="draft",
        total_planned_minutes=total_planned,
        total_break_minutes=total_break,
        total_buffer_minutes=total_buffer,
        blocks=blocks,
        deferred_tasks=plan_result.get("deferred_tasks", []),
        assumptions=plan_result.get("assumptions", []),
        explanation=plan_result.get("explanation", ""),
    )

    if review_result.get("objections"):
        plan_item["reviewer_objections"] = review_result["objections"]

    put_item(plan_item)

    return {
        "plan": {
            "date": date,
            "revision": revision,
            "status": "draft",
            "blocks": blocks,
            "deferred_tasks": plan_result.get("deferred_tasks", []),
            "explanation": plan_result.get("explanation", ""),
            "reviewer_objections": review_result.get("objections", []),
            "validation": validation,
        }
    }


# --- Replan ---

def process_plan_replan(user_id, job_input):
    date = job_input.get("date", today_str())
    reason = job_input.get("reason", "Schedule changed")
    ctx = _get_user_context(user_id)

    existing_plans = query_pk(f"USER#{user_id}", sk_prefix=f"PLAN#{date}#")
    revision = len(existing_plans)

    current_blocks = ctx.get("existing_blocks", [])
    completed = [b for b in current_blocks if b.get("status") == "completed"]
    locked = [b for b in current_blocks if b.get("locked")]

    replan_input = json.dumps({
        "date": date,
        "reason": reason,
        "completed_blocks": completed,
        "locked_blocks": locked,
        "all_current_blocks": current_blocks,
        "availability": ctx["profile"]["availability"],
        "tasks": ctx["tasks"],
        "planning_mode": ctx["profile"]["planning_mode"],
    }, default=str)

    messages = [{"role": "user", "content": [{"text": f"Replan for {date}. Reason: {reason}\n\n{replan_input}"}]}]
    plan_result = converse_json(prompts.REPLAN_SYSTEM, messages, max_tokens=4096, temperature=0.3)

    blocks = plan_result.get("blocks", [])
    for b in blocks:
        if not b.get("block_id"):
            b["block_id"] = generate_id()

    total_planned = sum(_block_duration(b) for b in blocks if b.get("block_type") == "task")

    plan_item = build_daily_plan(
        user_id, date, revision=revision,
        status="draft",
        total_planned_minutes=total_planned,
        blocks=blocks,
        deferred_tasks=plan_result.get("deferred_tasks", []),
        explanation=plan_result.get("explanation", ""),
        changes_from_previous=plan_result.get("changes_from_previous", []),
    )
    put_item(plan_item)

    return {
        "plan": {
            "date": date,
            "revision": revision,
            "status": "draft",
            "blocks": blocks,
            "changes_from_previous": plan_result.get("changes_from_previous", []),
            "explanation": plan_result.get("explanation", ""),
        }
    }


# --- Daily Report ---

def process_report_daily(user_id, job_input):
    date = job_input.get("date", today_str())
    ctx = _get_user_context(user_id)

    blocks = query_gsi("GSI2", f"USER#{user_id}", sk_prefix=f"DATE#{date}#BLOCK")
    block_list = [b for b in blocks if b.get("SK", "").startswith("BLOCK#")]

    plans = query_pk(f"USER#{user_id}", sk_prefix=f"PLAN#{date}#")
    accepted = [p for p in plans if p.get("status") == "accepted"]
    plan = accepted[0] if accepted else (plans[0] if plans else None)
    planned_blocks = plan.get("blocks", []) if plan else []

    completed_blocks = [b for b in block_list if b.get("status") == "completed"]
    tasks_done = query_gsi("GSI1", f"USER#{user_id}", sk_prefix="TASKSTATUS#done#")
    today_done = [t for t in tasks_done if (t.get("completed_at") or "").startswith(date)]

    habits = query_pk(f"USER#{user_id}", sk_prefix="HABIT#")
    logs = query_pk(f"USER#{user_id}", sk_prefix=f"HABITLOG#{date}#")
    habits_total = len([h for h in habits if h.get("SK", "").startswith("HABIT#")])
    habits_completed = len([l for l in logs if l.get("completed")])

    report_input = json.dumps({
        "date": date,
        "planned_blocks": planned_blocks,
        "actual_blocks": [{
            "title": b.get("title"),
            "status": b.get("status"),
            "block_type": b.get("block_type"),
        } for b in block_list],
        "tasks_completed_today": [t.get("title") for t in today_done],
        "habits_completed": habits_completed,
        "habits_total": habits_total,
    }, default=str)

    messages = [{"role": "user", "content": [{"text": f"Generate end-of-day report for {date}:\n\n{report_input}"}]}]
    report_result = converse_json(prompts.REPORT_SYSTEM, messages, max_tokens=1200, temperature=0.3)

    report_item = build_daily_report(
        user_id, date,
        planned_tasks_count=len(planned_blocks),
        completed_tasks_count=len(today_done),
        habits_completed=habits_completed,
        habits_total=habits_total,
        accomplishments=report_result.get("accomplishments", []),
        ai_narrative=report_result.get("ai_narrative", ""),
        improvement_suggestion=report_result.get("improvement_suggestion", ""),
        tomorrow_adjustment=report_result.get("tomorrow_preview", ""),
    )
    put_item(report_item)

    return {
        "report": {
            "date": date,
            "accomplishments": report_result.get("accomplishments", []),
            "unfinished": report_result.get("unfinished", []),
            "comparison": report_result.get("comparison", "as_planned"),
            "ai_narrative": report_result.get("ai_narrative", ""),
            "improvement_suggestion": report_result.get("improvement_suggestion", ""),
            "habits_summary": report_result.get("habits_summary", ""),
        }
    }


# --- Onboard Process ---

def process_onboard(user_id, job_input):
    s3_key = job_input.get("s3_key", "")
    doc_id = job_input.get("doc_id", "")

    text = ""
    if s3_key:
        s3 = boto3.client("s3")
        bucket = os.environ.get("DOCS_BUCKET", "vida-docs")
        try:
            obj = s3.get_object(Bucket=bucket, Key=s3_key)
            text = obj["Body"].read().decode("utf-8", errors="replace")
        except Exception as e:
            logger.error(f"Failed to read S3 object: {e}")
            text = job_input.get("text", "")
    else:
        text = job_input.get("text", "")

    if not text:
        return {"error": "No text content to process"}

    text = text[:12000]

    messages = [{"role": "user", "content": [{"text": f"Extract structured data from this document:\n\n{text}"}]}]
    result = converse_json(prompts.ONBOARD_EXTRACT, messages, max_tokens=4096, temperature=0.1)

    return {
        "extraction": result,
        "doc_id": doc_id,
        "text_length": len(text),
    }


# --- Document Process ---

def process_document(user_id, job_input):
    doc_id = job_input.get("doc_id", "")

    doc = get_item(f"USER#{user_id}", f"DOC#{doc_id}")
    if not doc:
        return {"error": "Document not found"}

    s3_key = doc.get("s3_key", "")
    s3 = boto3.client("s3")
    bucket = os.environ.get("DOCS_BUCKET", "vida-docs")

    try:
        obj = s3.get_object(Bucket=bucket, Key=s3_key)
        text = obj["Body"].read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.error(f"Failed to read document: {e}")
        doc["kb_status"] = "failed"
        put_item(doc)
        return {"error": f"Failed to read document: {str(e)}"}

    extracted_key = f"{user_id}/extracted/{doc_id}.txt"
    s3.put_object(Bucket=bucket, Key=extracted_key, Body=text.encode("utf-8"), ContentType="text/plain")

    doc["extracted_text_s3_key"] = extracted_key
    doc["kb_status"] = "indexed"
    put_item(doc)

    return {
        "doc_id": doc_id,
        "status": "indexed",
        "text_length": len(text),
    }


# --- Validator (code, not AI) ---

def _validate_plan(plan, ctx):
    errors = []
    warnings = []
    blocks = plan.get("blocks", [])

    for i, b in enumerate(blocks):
        if not b.get("start_time") or not b.get("end_time"):
            errors.append(f"Block {i} missing start_time or end_time")
            continue
        dur = _block_duration(b)
        if dur <= 0:
            errors.append(f"Block '{b.get('title', i)}' has non-positive duration")
        if dur > 180:
            warnings.append(f"Block '{b.get('title', i)}' is {dur}min (>3hrs continuous)")

    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            if _blocks_overlap(blocks[i], blocks[j]):
                errors.append(f"Overlap: '{blocks[i].get('title', i)}' and '{blocks[j].get('title', j)}'")

    locked = [b for b in ctx.get("existing_blocks", []) if b.get("locked")]
    for lb in locked:
        for b in blocks:
            if b.get("block_id") != lb.get("block_id") and _blocks_overlap(b, lb):
                errors.append(f"Block '{b.get('title')}' conflicts with locked block '{lb.get('title')}'")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def _block_duration(block):
    try:
        sh, sm = map(int, block["start_time"].split(":"))
        eh, em = map(int, block["end_time"].split(":"))
        return (eh * 60 + em) - (sh * 60 + sm)
    except (ValueError, KeyError):
        return 0


def _blocks_overlap(a, b):
    try:
        a_start = _time_to_min(a["start_time"])
        a_end = _time_to_min(a["end_time"])
        b_start = _time_to_min(b["start_time"])
        b_end = _time_to_min(b["end_time"])
        return a_start < b_end and b_start < a_end
    except (ValueError, KeyError):
        return False


def _time_to_min(t):
    h, m = map(int, t.split(":"))
    return h * 60 + m
