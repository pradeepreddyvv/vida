import json
import os
import time
from datetime import datetime, timezone, date


def generate_id():
    from ulid import ULID
    return str(ULID())


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
    headers = event.get("headers", {})
    user_id = headers.get("x-user-id") or headers.get("X-User-Id")
    if not user_id:
        auth = headers.get("authorization", "")
        if auth.startswith("Bearer "):
            user_id = auth[7:]
    return user_id or "anonymous"


def get_path_param(event, name):
    params = event.get("_path_params", {})
    if params.get(name):
        return params[name]
    path_params = event.get("pathParameters") or {}
    return path_params.get(name, "")


def get_query_param(event, name, default=None):
    params = event.get("queryStringParameters") or {}
    return params.get(name, default)
