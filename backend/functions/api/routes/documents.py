import os
import boto3
from shared.db import query_pk, put_item
from shared.models import build_document
from shared.utils import response, parse_body, generate_id


def list_documents(event, user_id):
    items = query_pk(f"USER#{user_id}", sk_prefix="DOC#")
    docs = []
    for item in items:
        doc_id = item["SK"].replace("DOC#", "")
        docs.append({
            "doc_id": doc_id,
            "source": item.get("source"),
            "notion_id": item.get("notion_id"),
            "goal_id": item.get("goal_id"),
            "text": item.get("extracted_text", "") if item.get("source") == "note" else "",
            "file_name": item.get("file_name"),
            "file_type": item.get("file_type"),
            "file_size_bytes": item.get("file_size_bytes", 0),
            "kb_status": item.get("kb_status", "pending"),
            "is_master": item.get("is_master", False),
            "created_at": item.get("created_at"),
        })
    return response(200, {"documents": docs})


def presign(event, user_id):
    body = parse_body(event)
    file_name = body.get("file_name", "document.txt")
    content_type = body.get("content_type") or body.get("file_type", "text/plain")
    ct_map = {"pdf": "application/pdf", "md": "text/markdown", "txt": "text/plain"}
    if content_type in ct_map:
        content_type = ct_map[content_type]

    doc_id = generate_id()
    ext = file_name.rsplit(".", 1)[-1] if "." in file_name else "txt"
    s3_key = f"uploads/{user_id}/{doc_id}/source.{ext}"

    region = os.environ.get("REGION", "us-east-2")
    s3 = boto3.client("s3", region_name=region, endpoint_url=f"https://s3.{region}.amazonaws.com")
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
        "file_name": file_name,
    })


def create_document(event, user_id):
    body = parse_body(event)
    doc_id = body.get("doc_id")
    if not doc_id:
        return response(400, {"error": {"code": "VALIDATION_ERROR", "message": "doc_id is required"}})

    s3_key = body.get("s3_key", "")
    if not s3_key.startswith(f"uploads/{user_id}/{doc_id}/"):
        return response(400, {"error": {"message": "Invalid document ownership"}})

    item = build_document(
        user_id,
        doc_id=doc_id,
        file_name=body.get("file_name", "document"),
        file_type=body.get("file_type", "txt"),
        file_size_bytes=body.get("file_size_bytes", 0),
        s3_key=body.get("s3_key", ""),
        is_master=body.get("is_master", False),
    )
    put_item(item)

    return response(201, {
        "doc_id": doc_id,
        "file_name": body.get("file_name"),
        "kb_status": "pending",
    })


def create_note(event, user_id):
    from shared.db import get_item
    body = parse_body(event)
    title = str(body.get('title', '')).strip()
    text = str(body.get('text', '')).strip()
    project = body.get('goal_id')
    if not title or not text or len(text.encode('utf-8')) > 100000:
        raise ValueError('A note needs a title and text (up to 100 KB).')
    if project and not get_item(f'USER#{user_id}', f'GOAL#{project}'):
        raise ValueError('Project not found')
    doc_id = generate_id()
    item = build_document(user_id, doc_id=doc_id, file_name=title, file_type='note', extracted_text=text, kb_status='indexed')
    item.update(source='note', goal_id=project)
    put_item(item)
    return response(201, {'doc_id':doc_id, 'title':title, 'kb_status':'indexed'})
