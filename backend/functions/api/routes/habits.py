from shared.db import query_pk, put_item, get_item
from shared.models import build_habit, build_habit_log
from shared.utils import response, parse_body, get_path_param, get_query_param, now_iso, today_str


def list_habits(event, user_id):
    habits = query_pk(f"USER#{user_id}", sk_prefix="HABIT#")
    date = get_query_param(event, "date", today_str())
    logs = query_pk(f"USER#{user_id}", sk_prefix=f"HABITLOG#{date}#")
    log_map = {}
    for log in logs:
        sk = log.get("SK", "")
        parts = sk.split("#")
        if len(parts) >= 3:
            log_map[parts[2]] = log.get("completed", False)

    result = []
    for h in habits:
        if not h.get("SK", "").startswith("HABIT#"):
            continue
        habit_id = h["SK"].replace("HABIT#", "")
        result.append({
            "habit_id": habit_id,
            "name": h.get("name"),
            "frequency": h.get("frequency", "daily"),
            "category": h.get("category", "general"),
            "reason": h.get("reason", ""),
            "completed_today": log_map.get(habit_id, False),
            "streak": h.get("streak", 0),
            "created_at": h.get("created_at"),
        })

    return response(200, {"habits": result, "date": date})


def create_habit(event, user_id):
    body = parse_body(event)
    if not body.get("name"):
        return response(400, {"error": {"code": "VALIDATION_ERROR", "message": "name is required"}})

    item = build_habit(user_id, **body)
    put_item(item)

    habit_id = item["SK"].replace("HABIT#", "")
    return response(201, {"habit_id": habit_id, "name": item.get("name")})


def update_habit(event, user_id):
    habit_id = get_path_param(event, "id")
    body = parse_body(event)

    existing = get_item(f"USER#{user_id}", f"HABIT#{habit_id}")
    if not existing:
        return response(404, {"error": {"code": "NOT_FOUND", "message": "Habit not found"}})

    allowed = {"name", "frequency", "category", "reason"}
    updates = {k: v for k, v in body.items() if k in allowed}
    updates["updated_at"] = now_iso()
    existing.update(updates)
    put_item(existing)

    return response(200, {"habit_id": habit_id, "name": existing.get("name")})


def log_habit(event, user_id):
    habit_id = get_path_param(event, "id")
    body = parse_body(event)
    date = body.get("date", today_str())
    completed = body.get("completed", True)

    existing = get_item(f"USER#{user_id}", f"HABIT#{habit_id}")
    if not existing:
        return response(404, {"error": {"code": "NOT_FOUND", "message": "Habit not found"}})

    log_item = build_habit_log(user_id, habit_id, date, completed)
    put_item(log_item)

    return response(200, {
        "habit_id": habit_id,
        "date": date,
        "completed": completed,
        "name": existing.get("name"),
    })
