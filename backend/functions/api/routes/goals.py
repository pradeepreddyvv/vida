from shared.db import query_pk, query_gsi, put_item, delete_item, get_item
from shared.models import build_goal
from shared.utils import response, parse_body, get_path_param, get_query_param, now_iso


def list_goals(event, user_id):
    status = get_query_param(event, "status")
    if status:
        items = query_gsi(
            "GSI1",
            f"USER#{user_id}",
            sk_prefix=f"GOALSTATUS#{status}#",
        )
    else:
        items = query_pk(f"USER#{user_id}", sk_prefix="GOAL#")

    goals = []
    for item in items:
        sk = item.get("SK", "")
        goal_id = sk.replace("GOAL#", "") if sk.startswith("GOAL#") else sk
        goals.append({
            "goal_id": goal_id,
            "title": item.get("title"),
            "description": item.get("description", ""),
            "target_date": item.get("target_date"),
            "status": item.get("status", "active"),
            "progress_pct": int(item.get("progress_pct") or 0),
            "category": item.get("category", "personal"),
            "priority": item.get("priority", "medium"),
            "milestones": item.get("milestones", []),
            "source": item.get("source", "manual"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        })

    return response(200, {"goals": goals})


def create_goal(event, user_id):
    body = parse_body(event)
    if not body.get("title"):
        return response(400, {"error": {"code": "VALIDATION_ERROR", "message": "title is required"}})

    item = build_goal(user_id, **body)
    put_item(item)

    goal_id = item["SK"].replace("GOAL#", "")
    return response(201, {"goal_id": goal_id, **_format_goal(item)})


def update_goal(event, user_id):
    goal_id = get_path_param(event, "id")
    body = parse_body(event)

    existing = get_item(f"USER#{user_id}", f"GOAL#{goal_id}")
    if not existing:
        return response(404, {"error": {"code": "NOT_FOUND", "message": "Goal not found"}})

    allowed = {"title", "description", "target_date", "status", "progress_pct", "category", "priority", "milestones"}
    updates = {k: v for k, v in body.items() if k in allowed}
    updates["updated_at"] = now_iso()

    existing.update(updates)
    if "status" in updates or "target_date" in updates:
        existing["GSI1SK"] = f"GOALSTATUS#{existing.get('status', 'active')}#{existing.get('target_date', '9999-12-31')}"

    put_item(existing)
    return response(200, {"goal_id": goal_id, **_format_goal(existing)})


def delete_goal(event, user_id):
    goal_id = get_path_param(event, "id")
    existing = get_item(f"USER#{user_id}", f"GOAL#{goal_id}")
    if not existing:
        return response(404, {"error": {"code": "NOT_FOUND", "message": "Goal not found"}})

    delete_item(f"USER#{user_id}", f"GOAL#{goal_id}")
    return response(200, {"deleted": True, "goal_id": goal_id})


def _format_goal(item):
    return {
        "title": item.get("title"),
        "description": item.get("description", ""),
        "target_date": item.get("target_date"),
        "status": item.get("status", "active"),
        "progress_pct": int(item.get("progress_pct") or 0),
        "category": item.get("category", "personal"),
        "priority": item.get("priority", "medium"),
        "milestones": item.get("milestones", []),
        "source": item.get("source", "manual"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }
