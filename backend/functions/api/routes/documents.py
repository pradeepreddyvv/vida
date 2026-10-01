import os
import boto3
from shared.db import query_pk
from shared.utils import response, parse_body, generate_id


def list_documents(event, user_id):
    items = query_pk(f"USER#{user_id}", sk_prefix="DOC#")
    docs = []
    for item in items:
        doc_id = item["SK"].replace("DOC#", "")
        docs.append({
            "doc_id": doc_id,
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
    file_type = body.get("file_type", "txt")

    doc_id = generate_id()
    s3_key = f"uploads/{user_id}/{doc_id}/source.{file_type}"

    s3 = boto3.client("s3", region_name=os.environ.get("REGION", "us-east-1"))
    bucket = os.environ.get("DOCS_BUCKET", "vida-docs")

    content_types = {
        "pdf": "application/pdf",
        "md": "text/markdown",
        "txt": "text/plain",
    }

    presigned = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": bucket,
            "Key": s3_key,
            "ContentType": content_types.get(file_type, "application/octet-stream"),
        },
        ExpiresIn=600,
    )

    return response(200, {
        "upload_url": presigned,
        "doc_id": doc_id,
        "s3_key": s3_key,
        "file_name": file_name,
    })
