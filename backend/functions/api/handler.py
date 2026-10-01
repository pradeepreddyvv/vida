import json
import logging
import re
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.utils import response, parse_body, get_user_id

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _import_routes():
    from api.routes import profile, goals, tasks, calendar, habits, journal, today, progress, onboard, plan, documents, integrations
    return {
        ("GET", "/api/profile"): profile.get_profile,
        ("PUT", "/api/profile"): profile.put_profile,
        ("PUT", "/api/profile/availability"): profile.put_availability,
        ("GET", "/api/goals"): goals.list_goals,
        ("POST", "/api/goals"): goals.create_goal,
        ("PUT", "/api/goals/{id}"): goals.update_goal,
        ("DELETE", "/api/goals/{id}"): goals.delete_goal,
        ("GET", "/api/tasks"): tasks.list_tasks,
        ("POST", "/api/tasks"): tasks.create_task,
        ("PUT", "/api/tasks/{id}"): tasks.update_task,
        ("DELETE", "/api/tasks/{id}"): tasks.delete_task,
        ("GET", "/api/calendar"): calendar.get_calendar,
        ("POST", "/api/calendar/blocks"): calendar.create_block,
        ("PUT", "/api/calendar/blocks/{id}"): calendar.update_block,
        ("DELETE", "/api/calendar/blocks/{id}"): calendar.delete_block,
        ("GET", "/api/habits"): habits.list_habits,
        ("POST", "/api/habits"): habits.create_habit,
        ("PUT", "/api/habits/{id}"): habits.update_habit,
        ("GET", "/api/journal"): journal.list_journal,
        ("POST", "/api/journal"): journal.create_journal,
        ("GET", "/api/today"): today.get_today,
        ("GET", "/api/progress"): progress.get_progress,
        ("GET", "/api/reports"): progress.list_reports,
        ("GET", "/api/reports/{date}"): progress.get_report,
        ("POST", "/api/onboard/presign"): onboard.presign,
        ("POST", "/api/onboard/confirm"): onboard.confirm,
        ("GET", "/api/plan/current"): plan.get_current_plan,
        ("POST", "/api/plan/accept"): plan.accept_plan,
        ("GET", "/api/documents"): documents.list_documents,
        ("POST", "/api/documents"): documents.create_document,
        ("POST", "/api/documents/presign"): documents.presign,
        ("GET", "/api/chat/history"): lambda e, u: _chat_history(e, u),
        # Async job submission routes
        ("POST", "/api/chat"): lambda e, u: _submit_job(e, u, "chat"),
        ("POST", "/api/plan/generate"): lambda e, u: _submit_job(e, u, "plan_generate"),
        ("POST", "/api/plan/replan"): lambda e, u: _submit_job(e, u, "plan_replan"),
        ("POST", "/api/reports/daily"): lambda e, u: _submit_job(e, u, "report_daily"),
        ("POST", "/api/onboard/process"): lambda e, u: _submit_job(e, u, "onboard_process"),
        ("POST", "/api/documents/process"): lambda e, u: _submit_job(e, u, "doc_process"),
        ("GET", "/api/jobs/{id}"): lambda e, u: _get_job(e, u),
        ("POST", "/api/habits/{id}/log"): habits.log_habit,
        # Integrations
        ("GET", "/api/auth/google"): integrations.start_google_auth,
        ("GET", "/api/auth/google/callback"): integrations.google_callback,
        ("GET", "/api/auth/notion"): integrations.start_notion_auth,
        ("GET", "/api/auth/notion/callback"): integrations.notion_callback,
        ("GET", "/api/integrations"): integrations.list_integrations,
        ("DELETE", "/api/integrations/{provider}"): integrations.disconnect_integration,
        ("POST", "/api/integrations/google/sync"): lambda e, u: _submit_job(e, u, "google_calendar_sync"),
        ("POST", "/api/integrations/notion/sync"): lambda e, u: _submit_job(e, u, "notion_sync"),
    }


ROUTES = None


def _get_routes():
    global ROUTES
    if ROUTES is None:
        ROUTES = _import_routes()
    return ROUTES


def _match_route(method, path):
    routes = _get_routes()
    handler = routes.get((method, path))
    if handler:
        return handler, {}
    for (route_method, route_path), route_handler in routes.items():
        if route_method != method:
            continue
        pattern = re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', route_path)
        match = re.fullmatch(pattern, path)
        if match:
            return route_handler, match.groupdict()
    return None, {}


def _submit_job(event, user_id, job_type):
    import boto3
    from shared.utils import generate_id, now_iso
    from shared.db import put_item

    body = parse_body(event)
    job_id = generate_id()

    put_item({
        "PK": f"USER#{user_id}",
        "SK": f"JOB#{job_id}",
        "job_type": job_type,
        "status": "pending",
        "input": body,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })

    lambda_client = boto3.client("lambda")
    lambda_client.invoke(
        FunctionName=os.environ.get("AI_FUNCTION_NAME", "vida-ai"),
        InvocationType="Event",
        Payload=json.dumps({
            "job_id": job_id,
            "job_type": job_type,
            "user_id": user_id,
            "input": body,
        }),
    )

    return response(202, {"job_id": job_id, "status": "pending"})


def _get_job(event, user_id):
    from shared.db import get_item
    from shared.utils import get_path_param

    job_id = get_path_param(event, "id")
    item = get_item(f"USER#{user_id}", f"JOB#{job_id}")
    if not item:
        return response(404, {"error": {"code": "NOT_FOUND", "message": "Job not found"}})

    result = {
        "job_id": job_id,
        "status": item.get("status", "pending"),
        "job_type": item.get("job_type"),
        "created_at": item.get("created_at"),
    }
    if item.get("status") == "completed":
        result["result"] = item.get("result", {})
    elif item.get("status") == "failed":
        result["error"] = item.get("error_message", "Unknown error")

    return response(200, result)


def _chat_history(event, user_id):
    from shared.db import query_pk
    from shared.utils import get_query_param

    session_id = get_query_param(event, "session_id", "default")
    items = query_pk(
        f"USER#{user_id}",
        sk_prefix=f"CHAT#{session_id}#",
        limit=50,
        scan_forward=False,
    )
    items.reverse()
    messages = [
        {
            "role": item.get("role"),
            "content": item.get("content"),
            "agent": item.get("agent"),
            "timestamp": item.get("created_at"),
        }
        for item in items
    ]
    return response(200, {"messages": messages})


def _create_session():
    import hashlib
    import secrets
    from shared.utils import generate_id, now_iso
    from shared.db import put_item
    from shared.models import build_profile

    user_id = generate_id()
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    profile = build_profile(user_id, onboarded=False)
    put_item(profile)

    put_item({
        "PK": "SESSIONS",
        "SK": f"TOKEN#{token_hash}",
        "user_id": user_id,
        "created_at": now_iso(),
    })

    return response(200, {
        "token": token,
        "user_id": user_id,
        "expires_at": "2026-12-31T23:59:59Z",
    })


def handler(event, context):
    try:
        method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
        raw_path = event.get("rawPath", "/")
        stage = event.get("requestContext", {}).get("stage", "")
        path = raw_path
        if stage and raw_path.startswith(f"/{stage}"):
            path = raw_path[len(f"/{stage}"):]
        if not path.startswith("/"):
            path = "/" + path

        if method == "OPTIONS":
            return response(200, {})

        if method == "POST" and path == "/api/session":
            return _create_session()

        OAUTH_CALLBACKS = ["/api/auth/google/callback", "/api/auth/notion/callback"]
        if path in OAUTH_CALLBACKS:
            route_handler, params = _match_route(method, path)
            if route_handler:
                if params:
                    event["_path_params"] = params
                return route_handler(event, None)
            return response(404, {"error": {"code": "NOT_FOUND", "message": "Not found"}})

        user_id = get_user_id(event)
        if not user_id:
            return response(401, {"error": {"code": "UNAUTHORIZED", "message": "Missing or invalid authentication"}})

        route_handler, params = _match_route(method, path)

        if not route_handler:
            return response(404, {"error": {"code": "NOT_FOUND", "message": f"No route: {method} {path}"}})

        if params:
            event["_path_params"] = params

        result = route_handler(event, user_id)

        if isinstance(result, dict) and "statusCode" in result:
            return result

        return result

    except json.JSONDecodeError:
        return response(400, {"error": {"code": "INVALID_JSON", "message": "Request body is not valid JSON"}})
    except Exception as e:
        logger.exception("Unhandled error")
        return response(500, {"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}})
