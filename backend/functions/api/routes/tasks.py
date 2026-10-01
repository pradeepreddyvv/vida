from shared.db import query_pk, query_gsi, put_item, delete_item, get_item
from shared.models import build_task
from shared.utils import response, parse_body, get_path_param, get_query_param, now_iso


def list_tasks(event, user_id):
    status = get_query_param(event, "status")
    goal_id = get_query_param(event, "goal_id")

    if goal_id:
        items = query_gsi(
            "GSI3",
            f"USER#{user_id}",
            sk_prefix=f"GOAL#{goal_id}#TASK#",
        )
    elif status:
        items = query_gsi(
            "GSI1",
            f"USER#{user_id}",
            sk_prefix=f"TASKSTATUS#{status}#",
        )
    else:
        items = query_pk(f"USER#{user_id}", sk_prefix="TASK#")

    tasks = [_format_task(item) for item in items]
    return response(200, {"tasks": tasks})


def create_task(event, user_id):
    body = parse_body(event)
    if not body.get("title"):
        return response(400, {"error": {"code": "VALIDATION_ERROR", "message": "title is required"}})

    item = build_task(user_id, **body)
    put_item(item)

    task_id = item["SK"].replace("TASK#", "")
    return response(201, {"task_id": task_id, **_format_task(item)})


def update_task(event, user_id):
    task_id = get_path_param(event, "id")
    body = parse_body(event)

    existing = get_item(f"USER#{user_id}", f"TASK#{task_id}")
    if not existing:
        return response(404, {"error": {"code": "NOT_FOUND", "message": "Task not found"}})

    allowed = {
        "title", "description", "due_date", "priority", "status",
        "goal_id", "remaining_minutes", "estimated_minutes",
        "energy_level", "splittable", "min_block_minutes",
        "dependency_ids", "category",
    }
    updates = {k: v for k, v in body.items() if k in allowed}
    updates["updated_at"] = now_iso()

    existing.update(updates)

    status = existing.get("status", "todo")
    due_date = existing.get("due_date", "9999-12-31")
    existing["GSI1SK"] = f"TASKSTATUS#{status}#{due_date}"
    existing["GSI2SK"] = f"DATE#{due_date}#TASK#{task_id}"

    gid = existing.get("goal_id", "NONE")
    existing["GSI3SK"] = f"GOAL#{gid}#TASK#{task_id}"

    put_item(existing)
    return response(200, {"task_id": task_id, **_format_task(existing)})


def delete_task(event, user_id):
    task_id = get_path_param(event, "id")
    existing = get_item(f"USER#{user_id}", f"TASK#{task_id}")
    if not existing:
        return response(404, {"error": {"code": "NOT_FOUND", "message": "Task not found"}})

    delete_item(f"USER#{user_id}", f"TASK#{task_id}")
    return response(200, {"deleted": True, "task_id": task_id})


def _format_task(item):
    sk = item.get("SK", "")
    task_id = sk.replace("TASK#", "") if sk.startswith("TASK#") else sk
    return {
        "task_id": task_id,
        "title": item.get("title"),
        "description": item.get("description", ""),
        "due_date": item.get("due_date"),
        "priority": item.get("priority", "medium"),
        "status": item.get("status", "todo"),
        "goal_id": item.get("goal_id"),
        "remaining_minutes": item.get("remaining_minutes"),
        "estimated_minutes": item.get("estimated_minutes", 30),
        "energy_level": item.get("energy_level", "medium"),
        "splittable": item.get("splittable", False),
        "min_block_minutes": item.get("min_block_minutes", 15),
        "dependency_ids": item.get("dependency_ids", []),
        "category": item.get("category", "general"),
        "source": item.get("source", "manual"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }
