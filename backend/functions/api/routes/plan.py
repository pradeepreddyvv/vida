from shared.db import query_pk, query_gsi, get_item, put_item, batch_write
from shared.utils import response, parse_body, today_str, now_iso


def get_current_plan(event, user_id):
    date = today_str()
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
    date = body.get("date", today_str())
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

    items_to_write = []

    for p in plans:
        if p.get("status") == "accepted" and p.get("SK") != plan.get("SK"):
            p["status"] = "superseded"
            items_to_write.append(p)

    plan["status"] = "accepted"
    plan["accepted_at"] = now_iso()
    items_to_write.append(plan)

    existing_blocks = query_gsi("GSI2", f"USER#{user_id}", sk_prefix=f"DATE#{date}#BLOCK")
    completed_block_ids = set()
    for b in existing_blocks:
        if b.get("status") in ("completed", "in_progress") or b.get("locked"):
            completed_block_ids.add(b["SK"].replace("BLOCK#", ""))

    blocks = plan.get("blocks", [])
    if blocks:
        from shared.models import build_time_block
        for b in blocks:
            bid = b.get("block_id")
            if bid in completed_block_ids:
                continue
            item = build_time_block(
                user_id,
                block_id=bid,
                date=date,
                start_time=b.get("start_time"),
                end_time=b.get("end_time"),
                block_type=b.get("block_type", "task"),
                title=b.get("title", ""),
                task_id=b.get("task_id"),
                locked=b.get("locked", False),
                source="planner",
                plan_id=plan.get("plan_id"),
            )
            items_to_write.append(item)

    batch_write(items_to_write)

    return response(200, {
        "plan": _format_plan(plan),
        "blocks_created": len(blocks),
    })


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
