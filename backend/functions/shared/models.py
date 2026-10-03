from shared.utils import generate_id, now_iso, today_str


def build_profile(user_id, **kwargs):
    ts = now_iso()
    return {
        "PK": f"USER#{user_id}",
        "SK": "PROFILE",
        "name": kwargs.get("name", ""),
        "role": kwargs.get("role", ""),
        "summary": kwargs.get("summary", ""),
        "phase": kwargs.get("phase", "other"),
        "user_type": kwargs.get("user_type", "both"),
        "timezone": kwargs.get("timezone"),
        "availability": kwargs.get("availability", {}),
        "planning_focus_task_ids": kwargs.get("planning_focus_task_ids", []),
        "day_start": kwargs.get("day_start", "09:00"),
        "day_end": kwargs.get("day_end", "17:00"),
        "planning_mode": kwargs.get("planning_mode", "balanced"),
        "key_dates": kwargs.get("key_dates", []),
        "onboarded": kwargs.get("onboarded", False),
        "created_at": kwargs.get("created_at", ts),
        "updated_at": ts,
    }


def build_goal(user_id, **kwargs):
    goal_id = kwargs.get("goal_id") or generate_id()
    ts = now_iso()
    status = kwargs.get("status", "active")
    target_date = kwargs.get("target_date", "9999-12-31")
    return {
        "PK": f"USER#{user_id}",
        "SK": f"GOAL#{goal_id}",
        "GSI1PK": f"USER#{user_id}",
        "GSI1SK": f"GOALSTATUS#{status}#{target_date}",
        "GSI3PK": f"USER#{user_id}",
        "GSI3SK": f"GOAL#{goal_id}",
        "title": kwargs.get("title", ""),
        "description": kwargs.get("description", ""),
        "target_date": target_date if target_date != "9999-12-31" else None,
        "status": status,
        "progress_pct": kwargs.get("progress_pct"),
        "category": kwargs.get("category", "personal"),
        "priority": kwargs.get("priority", "medium"),
        "milestones": kwargs.get("milestones", []),
        "source": kwargs.get("source", "manual"),
        "created_at": kwargs.get("created_at", ts),
        "updated_at": ts,
    }


def build_task(user_id, **kwargs):
    task_id = kwargs.get("task_id") or generate_id()
    ts = now_iso()
    status = kwargs.get("status", "todo")
    due_date = kwargs.get("due_date") or "9999-12-31"
    goal_id = kwargs.get("goal_id") or "NONE"
    est = kwargs.get("estimated_minutes")
    return {
        "PK": f"USER#{user_id}",
        "SK": f"TASK#{task_id}",
        "GSI1PK": f"USER#{user_id}",
        "GSI1SK": f"TASKSTATUS#{status}#{due_date}",
        "GSI2PK": f"USER#{user_id}",
        "GSI2SK": f"DATE#{due_date}#TASK#{task_id}",
        "GSI3PK": f"USER#{user_id}",
        "GSI3SK": f"GOAL#{goal_id}#TASK#{task_id}",
        "title": kwargs.get("title", ""),
        "description": kwargs.get("description", ""),
        "due_date": due_date if due_date != "9999-12-31" else None,
        "deadline_at": kwargs.get("deadline_at"),
        "status": status,
        "priority": kwargs.get("priority", "medium"),
        "goal_id": kwargs.get("goal_id"),
        "estimated_minutes": est,
        "remaining_minutes": kwargs.get("remaining_minutes", est),
        "energy": kwargs.get("energy", "any"),
        "splittable": kwargs.get("splittable", False),
        "min_block_minutes": kwargs.get("min_block_minutes", 15),
        "dependency_ids": kwargs.get("dependency_ids", []),
        "completed_at": kwargs.get("completed_at"),
        "source": kwargs.get("source", "manual"),
        "created_at": kwargs.get("created_at", ts),
        "updated_at": ts,
    }


def build_time_block(user_id, **kwargs):
    block_id = kwargs.get("block_id") or generate_id()
    ts = now_iso()
    date = kwargs.get("date", today_str())
    start_time = kwargs.get("start_time", "09:00")
    end_time = kwargs.get("end_time", "10:00")
    start_parts = start_time.split(":")
    end_parts = end_time.split(":")
    duration = (int(end_parts[0]) * 60 + int(end_parts[1])) - (int(start_parts[0]) * 60 + int(start_parts[1]))
    return {
        "PK": f"USER#{user_id}",
        "SK": f"BLOCK#{block_id}",
        "GSI2PK": f"USER#{user_id}",
        "GSI2SK": f"DATE#{date}#BLOCK#{start_time}",
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "duration_minutes": max(0, duration),
        "block_type": kwargs.get("block_type", "busy"),
        "title": kwargs.get("title", ""),
        "task_id": kwargs.get("task_id"),
        "locked": kwargs.get("locked", False),
        "status": kwargs.get("status", "scheduled"),
        "source": kwargs.get("source", "manual"),
        "plan_id": kwargs.get("plan_id"),
        "created_at": kwargs.get("created_at", ts),
        "updated_at": ts,
    }


def build_habit(user_id, **kwargs):
    habit_id = kwargs.get("habit_id") or generate_id()
    ts = now_iso()
    return {
        "PK": f"USER#{user_id}",
        "SK": f"HABIT#{habit_id}",
        "name": kwargs.get("name", ""),
        "frequency": kwargs.get("frequency", "daily"),
        "category": kwargs.get("category", "other"),
        "reason": kwargs.get("reason", ""),
        "active": kwargs.get("active", True),
        "streak_current": kwargs.get("streak_current", 0),
        "streak_best": kwargs.get("streak_best", 0),
        "source": kwargs.get("source", "manual"),
        "created_at": kwargs.get("created_at", ts),
        "updated_at": ts,
    }


def build_habit_log(user_id, habit_id, date, completed=True):
    ts = now_iso()
    return {
        "PK": f"USER#{user_id}",
        "SK": f"HABITLOG#{date}#{habit_id}",
        "GSI2PK": f"USER#{user_id}",
        "GSI2SK": f"DATE#{date}#HABITLOG#{habit_id}",
        "GSI3PK": f"USER#{user_id}",
        "GSI3SK": f"HABIT#{habit_id}#LOG#{date}",
        "habit_id": habit_id,
        "date": date,
        "completed": completed,
        "completed_at": ts if completed else None,
        "note": "",
    }


def build_journal(user_id, date, **kwargs):
    entry_id = generate_id()
    ts = now_iso()
    return {
        "PK": f"USER#{user_id}",
        "SK": f"JOURNAL#{date}#{entry_id}",
        "GSI2PK": f"USER#{user_id}",
        "GSI2SK": f"DATE#{date}#JOURNAL#{entry_id}",
        "date": date,
        "entry_text": kwargs.get("entry_text", ""),
        "ai_summary": kwargs.get("ai_summary"),
        "mood": kwargs.get("mood"),
        "extracted_items": kwargs.get("extracted_items", []),
        "created_at": ts,
    }


def build_chat_message(user_id, session_id, role, content, **kwargs):
    from shared.utils import timestamp_ms
    ts_ms = timestamp_ms() + "-" + generate_id()
    ts = now_iso()
    date = today_str()
    return {
        "PK": f"USER#{user_id}",
        "SK": f"CHAT#{session_id}#{ts_ms}",
        "GSI2PK": f"USER#{user_id}",
        "GSI2SK": f"DATE#{date}#CHAT#{ts_ms}",
        "session_id": session_id,
        "role": role,
        "content": content,
        "agent": kwargs.get("agent"),
        "actions_taken": kwargs.get("actions_taken", []),
        "tool_calls": kwargs.get("tool_calls", []),
        "created_at": ts,
    }


def build_document(user_id, **kwargs):
    doc_id = kwargs.get("doc_id") or generate_id()
    ts = now_iso()
    return {
        "PK": f"USER#{user_id}",
        "SK": f"DOC#{doc_id}",
        "file_name": kwargs.get("file_name", ""),
        "file_type": kwargs.get("file_type", "txt"),
        "s3_key": kwargs.get("s3_key", ""),
        "file_size_bytes": kwargs.get("file_size_bytes", 0),
        "extracted_text": kwargs.get("extracted_text", ""),
        "extracted_text_s3_key": kwargs.get("extracted_text_s3_key", ""),
        "kb_status": kwargs.get("kb_status", "pending"),
        "is_master": kwargs.get("is_master", False),
        "created_at": ts,
    }


def build_daily_plan(user_id, date, revision=0, **kwargs):
    plan_id = kwargs.get("plan_id") or generate_id()
    ts = now_iso()
    rev_str = str(revision).zfill(6)
    return {
        "PK": f"USER#{user_id}",
        "SK": f"PLAN#{date}#{rev_str}",
        "GSI2PK": f"USER#{user_id}",
        "GSI2SK": f"DATE#{date}#PLAN#{rev_str}",
        "date": date,
        "revision": revision,
        "plan_id": plan_id,
        "status": kwargs.get("status", "draft"),
        "total_available_minutes": kwargs.get("total_available_minutes", 0),
        "total_planned_minutes": kwargs.get("total_planned_minutes", 0),
        "total_break_minutes": kwargs.get("total_break_minutes", 0),
        "total_buffer_minutes": kwargs.get("total_buffer_minutes", 0),
        "blocks": kwargs.get("blocks", []),
        "deferred_tasks": kwargs.get("deferred_tasks", []),
        "assumptions": kwargs.get("assumptions", []),
        "explanation": kwargs.get("explanation", ""),
        "changes_from_previous": kwargs.get("changes_from_previous", []),
        "reviewer_objections": kwargs.get("reviewer_objections", []),
        "accepted_at": kwargs.get("accepted_at"),
        "created_at": ts,
    }


def build_daily_report(user_id, date, **kwargs):
    ts = now_iso()
    return {
        "PK": f"USER#{user_id}",
        "SK": f"REPORT#{date}",
        "GSI2PK": f"USER#{user_id}",
        "GSI2SK": f"DATE#{date}#REPORT",
        "date": date,
        "planned_tasks_count": kwargs.get("planned_tasks_count", 0),
        "planned_completed_tasks_count": kwargs.get("planned_completed_tasks_count"),
        "completed_tasks_count": kwargs.get("completed_tasks_count", 0),
        "unplanned_completed": kwargs.get("unplanned_completed", 0),
        "deferred_tasks": kwargs.get("deferred_tasks", []),
        "habits_completed": kwargs.get("habits_completed", 0),
        "habits_total": kwargs.get("habits_total", 0),
        "total_planned_minutes": kwargs.get("total_planned_minutes", 0),
        "total_actual_minutes": kwargs.get("total_actual_minutes"),
        "accomplishments": kwargs.get("accomplishments", []),
        "blockers": kwargs.get("blockers", []),
        "comparison_yesterday": kwargs.get("comparison_yesterday"),
        "ai_narrative": kwargs.get("ai_narrative", ""),
        "improvement_suggestion": kwargs.get("improvement_suggestion", ""),
        "tomorrow_adjustment": kwargs.get("tomorrow_adjustment", ""),
        "plan_snapshot_revision": kwargs.get("plan_snapshot_revision", 0),
        "created_at": ts,
    }


def build_skill(user_id, **kwargs):
    skill_id = kwargs.get("skill_id") or generate_id()
    ts = now_iso()
    return {
        "PK": f"USER#{user_id}",
        "SK": f"SKILL#{skill_id}",
        "name": kwargs.get("name", ""),
        "category": kwargs.get("category", "technical"),
        "proficiency": kwargs.get("proficiency"),
        "evidence_type": kwargs.get("evidence_type", "mentioned"),
        "evidence_source": kwargs.get("evidence_source", ""),
        "goal_id": kwargs.get("goal_id"),
        "source": kwargs.get("source", "manual"),
        "created_at": kwargs.get("created_at", ts),
        "updated_at": ts,
    }
