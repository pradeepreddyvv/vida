from shared.db import query_gsi, put_item, delete_item, get_item
from shared.models import build_time_block
from shared.utils import response, parse_body, get_path_param, get_query_param, now_iso, today_str


def get_calendar(event, user_id):
    date = get_query_param(event, "date", today_str())
    end_date = get_query_param(event, "end_date", date)

    items = query_gsi(
        "GSI2",
        f"USER#{user_id}",
        sk_prefix=f"DATE#{date}",
    )

    if end_date != date:
        from shared.db import query_pk
        all_items = query_pk(f"USER#{user_id}", sk_prefix="BLOCK#")
        items = [i for i in all_items if date <= i.get("date", "") <= end_date]

    blocks = [_format_block(item) for item in items if item.get("SK", "").startswith("BLOCK#")]
    blocks.sort(key=lambda b: b.get("start_time", ""))
    return response(200, {"date": date, "blocks": blocks})


def create_block(event, user_id):
    body = parse_body(event)
    required = ["date", "start_time", "end_time", "title", "block_type"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return response(400, {"error": {"code": "VALIDATION_ERROR", "message": f"Missing: {', '.join(missing)}"}})

    if body["block_type"] not in ("busy", "task", "break", "buffer"):
        return response(400, {"error": {"code": "VALIDATION_ERROR", "message": "block_type must be: busy, task, break, buffer"}})

    item = build_time_block(user_id, **body)
    put_item(item)

    block_id = item["SK"].replace("BLOCK#", "")
    return response(201, {"block_id": block_id, **_format_block(item)})


def update_block(event, user_id):
    block_id = get_path_param(event, "id")
    body = parse_body(event)

    existing = get_item(f"USER#{user_id}", f"BLOCK#{block_id}")
    if not existing:
        return response(404, {"error": {"code": "NOT_FOUND", "message": "Block not found"}})

    allowed = {"date", "start_time", "end_time", "title", "block_type", "task_id", "locked", "status"}
    updates = {k: v for k, v in body.items() if k in allowed}
    updates["updated_at"] = now_iso()

    existing.update(updates)
    if "date" in updates or "start_time" in updates:
        existing["GSI2SK"] = f"DATE#{existing['date']}#BLOCK#{existing['start_time']}"

    put_item(existing)
    return response(200, {"block_id": block_id, **_format_block(existing)})


def delete_block(event, user_id):
    block_id = get_path_param(event, "id")
    existing = get_item(f"USER#{user_id}", f"BLOCK#{block_id}")
    if not existing:
        return response(404, {"error": {"code": "NOT_FOUND", "message": "Block not found"}})

    delete_item(f"USER#{user_id}", f"BLOCK#{block_id}")
    return response(200, {"deleted": True, "block_id": block_id})


def _format_block(item):
    sk = item.get("SK", "")
    block_id = sk.replace("BLOCK#", "") if sk.startswith("BLOCK#") else sk
    return {
        "block_id": block_id,
        "date": item.get("date"),
        "start_time": item.get("start_time"),
        "end_time": item.get("end_time"),
        "duration_minutes": item.get("duration_minutes"),
        "block_type": item.get("block_type"),
        "title": item.get("title"),
        "task_id": item.get("task_id"),
        "locked": item.get("locked", False),
        "status": item.get("status", "scheduled"),
        "source": item.get("source", "manual"),
        "plan_id": item.get("plan_id"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }
