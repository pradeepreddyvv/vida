import json
import logging
import os
import sys
import traceback
import time
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.db import get_item, update_item, _get_table
from shared.utils import now_iso

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DISPATCHERS = {
    "chat": "process_chat",
    "action_execute": "process_action_execute",
    "plan_generate": "process_plan_generate",
    "plan_replan": "process_plan_replan",
    "report_daily": "process_report_daily",
    "onboard_process": "process_onboard",
    "doc_process": "process_document",
    "google_calendar_sync": "process_google_calendar_sync",
    "notion_sync": "process_notion_sync",
}


def handler(event, context):
    if event.get('operation') == 'notion_mirror':
        from shared.notion_mirror import sync
        return sync(event['user_id'])

    if event.get('operation') == 'workflow_step':
        from api.routes.workflows import run_step
        return run_step(event)
    job_id = event.get("job_id")
    user_id = event.get("user_id")
    job_type = event.get("job_type")

    logger.info(f"vida-ai invoked: job_id={job_id} type={job_type} user={user_id}")

    if not job_id or not user_id:
        logger.error("Missing job_id or user_id")
        return {"error": "Missing job_id or user_id"}

    job = get_item(f"USER#{user_id}", f"JOB#{job_id}")
    if not job:
        logger.error(f"Job not found: {job_id}")
        return {"error": "Job not found"}

    if job.get("status") != "pending":
        logger.warning(f"Job {job_id} not pending, status={job.get('status')}")
        return {"status": job.get("status")}

    remaining = math.ceil(context.get_remaining_time_in_millis()/1000) if context else 180
    table = _get_table()
    try:
        table.update_item(Key={"PK":f"USER#{user_id}", "SK":f"JOB#{job_id}"},
            UpdateExpression="SET #s = :running, updated_at = :now, deadline = :deadline, #stage = :stage",
            ConditionExpression="#s = :pending",
            ExpressionAttributeNames={"#s":"status", "#stage":"stage"},
            ExpressionAttributeValues={":running":"processing", ":pending":"pending", ":now":now_iso(), ":deadline":int(time.time())+remaining+10, ":stage":"Checking your saved context"})
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return {"status":"already_claimed"}
    job_type = job.get("type", job.get("job_type", job_type))

    try:
        func_name = DISPATCHERS.get(job_type)
        if not func_name:
            raise ValueError(f"Unknown job type: {job_type}")

        from shared import agents
        processor = getattr(agents, func_name)
        from shared.planning_lock import agent_lock
        from shared.job_progress import tracking
        with agent_lock(user_id, resource=job_type, lease_seconds=remaining+10), tracking(user_id, job_id):
            result = processor(user_id, job.get("input", {}))
        if isinstance(result, dict) and result.get("error"):
            raise ValueError(result["error"])

        update_item(f"USER#{user_id}", f"JOB#{job_id}", {
            "status": "completed",
            "result": result,
            "updated_at": now_iso(),
        })

        logger.info(f"Job {job_id} completed")
        return {"status": "completed", "job_id": job_id}

    except Exception as e:
        logger.error(f"Job {job_id} failed: {traceback.format_exc()}")
        update_item(f"USER#{user_id}", f"JOB#{job_id}", {
            "status": "failed",
            "error_message": str(e),
            "updated_at": now_iso(),
        })
        return {"status": "failed", "error": str(e)}
