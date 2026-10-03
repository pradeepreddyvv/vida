from shared.db import get_item, put_item
from shared.models import build_profile
from shared.utils import response, parse_body, now_iso


def get_profile(event, user_id):
    item = get_item(f"USER#{user_id}", "PROFILE")
    if not item:
        return response(200, {"profile": None, "onboarded": False})

    return response(200, {"profile": _format_profile(item)})


def put_profile(event, user_id):
    body = parse_body(event)
    if "planning_focus_task_ids" in body:
        ids = body["planning_focus_task_ids"]
        if not isinstance(ids,list) or len(ids)>50 or any(not isinstance(x,str) for x in ids): raise ValueError("Choose up to 50 focus tasks.")
    if "day_start" in body or "day_end" in body:
        from shared.plan_validation import minutes
        if minutes(body.get("day_start","09:00")) >= minutes(body.get("day_end","17:00")): raise ValueError("End time must be after start time.")
    existing = get_item(f"USER#{user_id}", "PROFILE")

    if existing:
        allowed = {
            "name", "role", "summary", "phase", "user_type",
            "timezone", "planning_mode", "key_dates", "planning_focus_task_ids", "day_start", "day_end",
        }
        updates = {k: v for k, v in body.items() if k in allowed}
        updates["updated_at"] = now_iso()
        existing.update(updates)
        put_item(existing)
        return response(200, {"profile": _format_profile(existing)})
    else:
        item = build_profile(user_id, **body)
        put_item(item)
        return response(201, {"profile": _format_profile(item)})


def put_availability(event, user_id):
    body = parse_body(event)
    existing = get_item(f"USER#{user_id}", "PROFILE")
    if not existing:
        return response(404, {"error": {"code": "NOT_FOUND", "message": "Profile not found. Complete onboarding first."}})

    existing["availability"] = body.get("availability", existing.get("availability"))
    existing["updated_at"] = now_iso()
    put_item(existing)
    return response(200, {"profile": _format_profile(existing)})


def _format_profile(item):
    return {
        "sample_data": item.get("sample_data", False),
        "demo_profile": item.get("demo_profile"),
        "name": item.get("name", ""),
        "role": item.get("role", ""),
        "summary": item.get("summary", ""),
        "phase": item.get("phase", "other"),
        "user_type": item.get("user_type", "both"),
        "timezone": item.get("timezone", "America/Los_Angeles"),
        "availability": item.get("availability", {}),
        "planning_focus_task_ids": item.get("planning_focus_task_ids", []),
        "day_start": item.get("day_start", "09:00"),
        "day_end": item.get("day_end", "17:00"),
        "planning_mode": item.get("planning_mode", "balanced"),
        "key_dates": item.get("key_dates", []),
        "onboarded": item.get("onboarded", False),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }
