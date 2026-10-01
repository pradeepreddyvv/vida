import os
import boto3
from shared.db import get_item, put_item
from shared.models import build_document
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

    s3 = boto3.client("s3", region_name=os.environ.get("REGION", "us-east-1"))
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
    doc_id = body.get("doc_id")
    s3_key = body.get("s3_key")
    file_name = body.get("file_name", "upload.txt")
    file_type = body.get("file_type", "txt")

    if not doc_id or not s3_key:
        return response(400, {"error": {"code": "VALIDATION_ERROR", "message": "doc_id and s3_key are required"}})

    item = build_document(
        user_id,
        doc_id=doc_id,
        file_name=file_name,
        file_type=file_type,
        s3_key=s3_key,
        is_master=True,
        kb_status="pending",
    )
    put_item(item)

    profile = get_item(f"USER#{user_id}", "PROFILE")
    if not profile:
        from shared.models import build_profile
        profile = build_profile(user_id, onboarded=False)
        put_item(profile)

    return response(200, {
        "doc_id": doc_id,
        "status": "confirmed",
        "message": "Document confirmed. Submit POST /api/onboard/process to start AI extraction.",
    })


def _content_type(file_type):
    types = {
        "pdf": "application/pdf",
        "md": "text/markdown",
        "txt": "text/plain",
    }
    return types.get(file_type, "application/octet-stream")
