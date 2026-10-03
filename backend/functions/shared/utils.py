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


def today_str(user_id=None):
    if user_id:
        from shared.db import get_item
        from zoneinfo import ZoneInfo
        profile = get_item(f"USER#{user_id}", "PROFILE") or {}
        return datetime.now(ZoneInfo(profile.get("timezone") or "UTC")).date().isoformat()
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
        "body": json.dumps(body, default=_json_default),
    }


def parse_body(event):
    body = event.get("body", "{}")
    if isinstance(body, str):
        return json.loads(body) if body else {}
    return body or {}


def _json_default(value):
    from decimal import Decimal
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def get_user_id(event):
    import hashlib
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    auth = headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    from shared.db import get_item
    token_hash = hashlib.sha256(auth[7:].encode()).hexdigest()
    session = get_item("SESSIONS", f"TOKEN#{token_hash}")
    if not session:
        return None
    expires = session.get("expires_at_epoch")
    if expires is None:
        # Bound legacy sessions rather than accepting them indefinitely.
        try:
            expires = datetime.fromisoformat(session["created_at"].replace("Z", "+00:00")).timestamp() + 86400
        except (KeyError, ValueError):
            return None
    return session.get("user_id") if float(expires) > time.time() else None


def get_path_param(event, name):
    params = event.get("_path_params", {})
    if params.get(name):
        return params[name]
    path_params = event.get("pathParameters") or {}
    return path_params.get(name, "")


def get_query_param(event, name, default=None):
    params = event.get("queryStringParameters") or {}
    return params.get(name, default)
