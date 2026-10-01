from shared.db import query_pk, query_gsi, get_item
from shared.utils import response, today_str


def get_today(event, user_id):
    date = today_str()

    profile = get_item(f"USER#{user_id}", "PROFILE")
    if not profile:
        return response(200, {"onboarded": False})

    tasks = query_gsi("GSI1", f"USER#{user_id}", sk_prefix="TASKSTATUS#todo#")
    tasks += query_gsi("GSI1", f"USER#{user_id}", sk_prefix="TASKSTATUS#in_progress#")

    active_tasks = []
    overdue = []
    due_today = []
    for t in tasks:
        if not t.get("SK", "").startswith("TASK#"):
            continue
        task_id = t["SK"].replace("TASK#", "")
        task = {
            "task_id": task_id,
            "title": t.get("title"),
            "due_date": t.get("due_date"),
            "priority": t.get("priority", "medium"),
            "status": t.get("status", "todo"),
            "estimated_minutes": t.get("estimated_minutes", 30),
            "goal_id": t.get("goal_id"),
        }
        dd = t.get("due_date") or "9999-12-31"
        if dd < date:
            overdue.append(task)
        elif dd == date:
            due_today.append(task)
        else:
            active_tasks.append(task)

    blocks = query_gsi("GSI2", f"USER#{user_id}", sk_prefix=f"DATE#{date}#BLOCK")
    today_blocks = []
    for b in blocks:
        if not b.get("SK", "").startswith("BLOCK#"):
            continue
        today_blocks.append({
            "block_id": b["SK"].replace("BLOCK#", ""),
            "start_time": b.get("start_time"),
            "end_time": b.get("end_time"),
            "title": b.get("title"),
            "block_type": b.get("block_type"),
            "task_id": b.get("task_id"),
            "locked": b.get("locked", False),
            "status": b.get("status", "scheduled"),
        })
    today_blocks.sort(key=lambda b: b.get("start_time", ""))

    habits = query_pk(f"USER#{user_id}", sk_prefix="HABIT#")
    logs = query_pk(f"USER#{user_id}", sk_prefix=f"HABITLOG#{date}#")
    log_set = set()
    for log in logs:
        if not log.get("completed", False):
            continue
        parts = log.get("SK", "").split("#")
        if len(parts) >= 3:
            log_set.add(parts[2])

    habit_list = []
    for h in habits:
        if not h.get("SK", "").startswith("HABIT#"):
            continue
        hid = h["SK"].replace("HABIT#", "")
        habit_list.append({
            "habit_id": hid,
            "name": h.get("name"),
            "completed_today": hid in log_set,
            "streak": h.get("streak", 0),
        })

    goals = query_gsi("GSI1", f"USER#{user_id}", sk_prefix="GOALSTATUS#active#")
    goal_list = []
    for g in goals:
        if not g.get("SK", "").startswith("GOAL#"):
            continue
        goal_list.append({
            "goal_id": g["SK"].replace("GOAL#", ""),
            "title": g.get("title"),
            "progress_pct": int(g.get("progress_pct") or 0),
        })

    scheduled_minutes = sum(b.get("duration_minutes", 0) or 0 for b in blocks if b.get("SK", "").startswith("BLOCK#"))
    availability = profile.get("availability", {})

    plan = query_pk(f"USER#{user_id}", sk_prefix=f"PLAN#{date}#")
    current_plan = None
    if plan:
        latest = max(plan, key=lambda p: p.get("SK", ""))
        if latest.get("status") == "accepted":
            current_plan = {
                "revision": latest.get("SK", "").split("#")[-1],
                "status": "accepted",
                "explanation": latest.get("explanation"),
            }

    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_actionable = overdue + due_today + active_tasks
    all_actionable.sort(key=lambda t: (priority_order.get(t.get("priority", "medium"), 2), t.get("due_date", "9999-12-31")))
    next_action = all_actionable[0] if all_actionable else None

    return response(200, {
        "date": date,
        "profile_name": profile.get("name", ""),
        "planning_mode": profile.get("planning_mode", "balanced"),
        "onboarded": True,
        "next_action": next_action,
        "blocks": today_blocks,
        "overdue_tasks": overdue,
        "due_today_tasks": due_today,
        "habits": habit_list,
        "goals": goal_list,
        "current_plan": current_plan,
        "capacity": {
            "scheduled_minutes": scheduled_minutes,
        },
    })
