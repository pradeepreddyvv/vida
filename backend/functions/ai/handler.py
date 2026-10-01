import json
import logging
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.db import get_item, update_item
from shared.utils import now_iso

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DISPATCHERS = {
    "chat": "process_chat",
    "plan_generate": "process_plan_generate",
    "plan_replan": "process_plan_replan",
    "report_daily": "process_report_daily",
    "onboard_process": "process_onboard",
    "doc_process": "process_document",
    "google_calendar_sync": "process_google_calendar_sync",
    "notion_sync": "process_notion_sync",
}


def handler(event, context):
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

    update_item(f"USER#{user_id}", f"JOB#{job_id}", {
        "status": "processing",
        "updated_at": now_iso(),
    })

    try:
        func_name = DISPATCHERS.get(job_type)
        if not func_name:
            raise ValueError(f"Unknown job type: {job_type}")

        from shared import agents
        processor = getattr(agents, func_name)
        result = processor(user_id, job.get("input", {}))

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
