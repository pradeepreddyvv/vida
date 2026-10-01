import os
import boto3
from shared.db import get_item, put_item, batch_write
from shared.models import build_document, build_goal, build_task, build_habit
from shared.utils import response, parse_body, generate_id, now_iso


def presign(event, user_id):
    body = parse_body(event)
    file_name = body.get("file_name", "upload.txt")
    content_type = body.get("content_type") or body.get("file_type", "text/plain")
    if content_type in ("txt", "md", "pdf"):
        content_type = _content_type(content_type)

    doc_id = generate_id()
    ext = file_name.rsplit(".", 1)[-1] if "." in file_name else "txt"
    s3_key = f"uploads/{user_id}/{doc_id}/source.{ext}"

    s3 = boto3.client("s3", region_name=os.environ.get("REGION", "us-east-2"))
    bucket = os.environ.get("DOCS_BUCKET", "vida-docs")

    presigned = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": bucket,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=600,
    )

    return response(200, {
        "upload_url": presigned,
        "doc_id": doc_id,
        "s3_key": s3_key,
    })


def confirm(event, user_id):
    body = parse_body(event)

    profile_data = body.get("profile", {})
    facts = body.get("facts", [])
    suggestions = body.get("suggestions", {})
    commitments = body.get("commitments", [])

    existing_profile = get_item(f"USER#{user_id}", "PROFILE")
    if existing_profile:
        existing_profile.update({
            "name": profile_data.get("name", existing_profile.get("name", "")),
            "role": profile_data.get("role", existing_profile.get("role", "")),
            "summary": profile_data.get("summary", existing_profile.get("summary", "")),
            "phase": profile_data.get("phase", existing_profile.get("phase", "other")),
            "onboarded": True,
            "updated_at": now_iso(),
        })
        profile_item = existing_profile
    else:
        from shared.models import build_profile
        profile_data["onboarded"] = True
        profile_item = build_profile(user_id, **profile_data)

    items_to_write = [profile_item]

    for g in suggestions.get("goals", []):
        items_to_write.append(build_goal(user_id, **g))

    for t in suggestions.get("tasks", []):
        items_to_write.append(build_task(user_id, **t))

    for h in suggestions.get("habits", []):
        items_to_write.append(build_habit(user_id, **h))

    for c in commitments:
        ctype = c.get("type", "task")
        if ctype == "task":
            items_to_write.append(build_task(
                user_id, title=c.get("title"), due_date=c.get("due_date"),
                priority=c.get("priority", "high"), source="onboard"))
        elif ctype == "goal":
            items_to_write.append(build_goal(
                user_id, title=c.get("title"), target_date=c.get("target_date"),
                source="onboard"))

    batch_write(items_to_write)

    return response(200, {
        "onboarded": True,
        "profile": {
            "name": profile_item.get("name"),
            "role": profile_item.get("role"),
            "onboarded": True,
        },
        "created": {
            "goals": len(suggestions.get("goals", [])) + sum(1 for c in commitments if c.get("type") == "goal"),
            "tasks": len(suggestions.get("tasks", [])) + sum(1 for c in commitments if c.get("type") == "task"),
            "habits": len(suggestions.get("habits", [])),
        },
    })


def _content_type(file_type):
    types = {
        "pdf": "application/pdf",
        "md": "text/markdown",
        "txt": "text/plain",
    }
    return types.get(file_type, "application/octet-stream")
