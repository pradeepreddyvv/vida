from shared.db import query_gsi, put_item
from shared.models import build_journal
from shared.utils import response, parse_body, get_query_param, today_str


def list_journal(event, user_id):
    date = get_query_param(event, "date")
    limit = int(get_query_param(event, "limit", "20"))

    if date:
        items = query_gsi("GSI2", f"USER#{user_id}", sk_prefix=f"DATE#{date}#JOURNAL")
    else:
        items = query_gsi("GSI2", f"USER#{user_id}", sk_prefix="DATE#", limit=limit)
        items = [i for i in items if "JOURNAL" in i.get("GSI2SK", "")]

    entries = []
    for item in items:
        sk = item.get("SK", "")
        parts = sk.split("#")
        entries.append({
            "date": item.get("date", parts[1] if len(parts) > 1 else ""),
            "entry_id": parts[2] if len(parts) > 2 else "",
            "entry_text": item.get("entry_text", ""),
            "ai_summary": item.get("ai_summary"),
            "mood": item.get("mood"),
            "extracted_items": item.get("extracted_items", []),
            "created_at": item.get("created_at"),
        })

    entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    return response(200, {"entries": entries[:limit]})


def create_journal(event, user_id):
    body = parse_body(event)
    if not body.get("entry_text"):
        return response(400, {"error": {"code": "VALIDATION_ERROR", "message": "entry_text is required"}})

    date = body.pop("date", None) or today_str()
    item = build_journal(user_id, date, **body)
    put_item(item)

    return response(201, {
        "date": date,
        "entry_text": body["entry_text"],
        "created_at": item.get("created_at"),
    })
