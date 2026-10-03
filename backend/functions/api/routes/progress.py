from shared.db import query_pk, query_gsi, get_item
from shared.utils import response, get_query_param, today_str


def get_progress(event, user_id):
    goals = query_pk(f"USER#{user_id}", sk_prefix="GOAL#")
    tasks = query_pk(f"USER#{user_id}", sk_prefix="TASK#")

    total_tasks = len(tasks)
    done_tasks = sum(1 for t in tasks if t.get("status") == "done")
    active_goals = [g for g in goals if g.get("status") == "active"]

    goal_summary = []
    for g in goals:
        gid = g["SK"].replace("GOAL#", "")
        linked_tasks = [t for t in tasks if t.get("goal_id") == gid]
        linked_done = sum(1 for t in linked_tasks if t.get("status") == "done")
        pct = int((linked_done / len(linked_tasks)) * 100) if linked_tasks else 0
        goal_summary.append({
            "goal_id": gid,
            "title": g.get("title"),
            "status": g.get("status"),
            "progress_pct": pct,
            "total_tasks": len(linked_tasks),
            "completed_tasks": linked_done,
            "category": g.get("category", "personal"),
            "target_date": g.get("target_date"),
        })

    habits = query_pk(f"USER#{user_id}", sk_prefix="HABIT#")
    habit_summary = []
    for h in habits:
        if not h.get("SK", "").startswith("HABIT#"):
            continue
        habit_summary.append({
            "habit_id": h["SK"].replace("HABIT#", ""),
            "name": h.get("name"),
            "streak_current": h.get("streak_current", 0),
            "streak_best": h.get("streak_best", 0),
            "active": h.get("active", True),
        })

    return response(200, {
        "goals": goal_summary,
        "tasks_total": total_tasks,
        "tasks_completed": done_tasks,
        "task_completion_pct": int((done_tasks / total_tasks) * 100) if total_tasks else 0,
        "active_goals_count": len(active_goals),
        "habits": habit_summary,
    })


def list_reports(event, user_id):
    limit = int(get_query_param(event, "limit", "14"))
    items = query_pk(f"USER#{user_id}", sk_prefix="REPORT#", limit=limit, scan_forward=False)
    reports = [i for i in items if "REPORT" in i.get("GSI2SK", "")][:limit]

    result = []
    for r in reports:
        result.append({
            "date": r.get("date"),
            "completed_tasks_count": r.get("completed_tasks_count", 0),
            "planned_tasks_count": r.get("planned_tasks_count", 0),
            "habits_completed": r.get("habits_completed", 0),
            "habits_total": r.get("habits_total", 0),
        })

    return response(200, {"reports": result})


def get_report(event, user_id):
    from shared.utils import get_path_param
    date = get_path_param(event, "date")
    item = get_item(f"USER#{user_id}", f"REPORT#{date}")
    if not item:
        return response(404, {"error": {"code": "NOT_FOUND", "message": "Report not found"}})

    return response(200, {
        "date": item.get("date"),
        "planned_tasks_count": item.get("planned_tasks_count", 0),
        "planned_completed_tasks_count": item.get("planned_completed_tasks_count"),
        "completed_tasks_count": item.get("completed_tasks_count", 0),
        "unplanned_completed": item.get("unplanned_completed", 0),
        "deferred_tasks": item.get("deferred_tasks", []),
        "habits_completed": item.get("habits_completed", 0),
        "habits_total": item.get("habits_total", 0),
        "total_planned_minutes": item.get("total_planned_minutes", 0),
        "total_actual_minutes": item.get("total_actual_minutes"),
        "accomplishments": item.get("accomplishments", []),
        "blockers": item.get("blockers", []),
        "comparison_yesterday": item.get("comparison_yesterday"),
        "ai_narrative": item.get("ai_narrative", ""),
        "improvement_suggestion": item.get("improvement_suggestion", ""),
        "tomorrow_adjustment": item.get("tomorrow_adjustment", ""),
        "created_at": item.get("created_at"),
    })
