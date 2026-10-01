import json
import os
import time
from datetime import datetime, timezone, date


def generate_id():
    import uuid
    ts = int(time.time() * 1000)
    return f"{ts:013x}-{uuid.uuid4().hex[:12]}"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_str():
    return date.today().isoformat()


def timestamp_ms():
    return str(int(time.time() * 1000))


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,X-User-Id",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps(body, default=str),
    }


def parse_body(event):
    body = event.get("body", "{}")
    if isinstance(body, str):
        return json.loads(body) if body else {}
    return body or {}


def get_user_id(event):
    import hashlib
    headers = event.get("headers", {})
    auth = headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        from shared.db import get_item
        session = get_item("SESSIONS", f"TOKEN#{token_hash}")
        if session:
            return session.get("user_id")
    user_id = headers.get("x-user-id") or headers.get("X-User-Id")
    if user_id:
        return user_id
    return None


def get_path_param(event, name):
    params = event.get("_path_params", {})
    if params.get(name):
        return params[name]
    path_params = event.get("pathParameters") or {}
    return path_params.get(name, "")


def get_query_param(event, name, default=None):
    params = event.get("queryStringParameters") or {}
    return params.get(name, default)
