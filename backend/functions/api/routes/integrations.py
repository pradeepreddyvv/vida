import json
import logging
import os
import urllib.parse
import urllib.request
import base64
from datetime import datetime, timedelta, timezone

from shared.db import get_item, put_item, query_pk, delete_item
from shared.utils import response, generate_id, now_iso, today_str, get_query_param, get_path_param
from shared.models import build_time_block, build_document

logger = logging.getLogger(__name__)

FRONTEND_URL = "https://dieldwu0y5z3o.cloudfront.net"
GOOGLE_REDIRECT_URI = f"{FRONTEND_URL}/api/auth/google/callback"
NOTION_REDIRECT_URI = f"{FRONTEND_URL}/api/auth/notion/callback"

GOOGLE_SCOPES = "https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email"


def _redirect(url):
    return {
        "statusCode": 302,
        "headers": {
            "Location": url,
            "Access-Control-Allow-Origin": "*",
        },
        "body": "",
    }


def _http_request(url, data=None, headers=None, method="GET"):
    if headers is None:
        headers = {}
    if data and isinstance(data, dict):
        data = json.dumps(data).encode("utf-8")
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
    elif data and isinstance(data, str):
        data = data.encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error(f"HTTP {e.code} from {url}: {body}")
        raise


# ──────────────────────────────────────────────
# Google Calendar OAuth
# ──────────────────────────────────────────────

def start_google_auth(event, user_id):
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    if not client_id:
        return response(400, {"error": "Google OAuth not configured"})

    state = generate_id()
    put_item({
        "PK": "OAUTH_STATE",
        "SK": f"STATE#{state}",
        "user_id": user_id,
        "provider": "google",
        "created_at": now_iso(),
    })

    params = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
    return response(200, {"url": auth_url})


def google_callback(event, _user_id):
    code = get_query_param(event, "code", "")
    state = get_query_param(event, "state", "")
    error = get_query_param(event, "error", "")

    if error:
        return _redirect(f"{FRONTEND_URL}/settings?error=google_denied")

    if not code or not state:
        return _redirect(f"{FRONTEND_URL}/settings?error=google_missing_params")

    state_item = get_item("OAUTH_STATE", f"STATE#{state}")
    if not state_item:
        return _redirect(f"{FRONTEND_URL}/settings?error=invalid_state")

    user_id = state_item["user_id"]
    delete_item("OAUTH_STATE", f"STATE#{state}")

    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")

    token_data = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            tokens = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.error(f"Google token exchange failed: {e}")
        return _redirect(f"{FRONTEND_URL}/settings?error=google_token_failed")

    expires_in = tokens.get("expires_in", 3600)
    expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

    put_item({
        "PK": f"USER#{user_id}",
        "SK": "INTEGRATION#google_calendar",
        "provider": "google_calendar",
        "access_token": tokens.get("access_token", ""),
        "refresh_token": tokens.get("refresh_token", ""),
        "token_expiry": expiry,
        "status": "connected",
        "connected_at": now_iso(),
    })

    return _redirect(f"{FRONTEND_URL}/settings?connected=google")


# ──────────────────────────────────────────────
# Notion OAuth
# ──────────────────────────────────────────────

def start_notion_auth(event, user_id):
    client_id = os.environ.get("NOTION_CLIENT_ID", "")
    if not client_id:
        return response(400, {"error": "Notion OAuth not configured"})

    state = generate_id()
    put_item({
        "PK": "OAUTH_STATE",
        "SK": f"STATE#{state}",
        "user_id": user_id,
        "provider": "notion",
        "created_at": now_iso(),
    })

    params = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": NOTION_REDIRECT_URI,
        "owner": "user",
        "state": state,
    })
    auth_url = f"https://api.notion.com/v1/oauth/authorize?{params}"
    return response(200, {"url": auth_url})


def notion_callback(event, _user_id):
    code = get_query_param(event, "code", "")
    state = get_query_param(event, "state", "")
    error = get_query_param(event, "error", "")

    if error:
        return _redirect(f"{FRONTEND_URL}/settings?error=notion_denied")

    if not code or not state:
        return _redirect(f"{FRONTEND_URL}/settings?error=notion_missing_params")

    state_item = get_item("OAUTH_STATE", f"STATE#{state}")
    if not state_item:
        return _redirect(f"{FRONTEND_URL}/settings?error=invalid_state")

    user_id = state_item["user_id"]
    delete_item("OAUTH_STATE", f"STATE#{state}")

    client_id = os.environ.get("NOTION_CLIENT_ID", "")
    client_secret = os.environ.get("NOTION_CLIENT_SECRET", "")
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    try:
        token_body = json.dumps({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": NOTION_REDIRECT_URI,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.notion.com/v1/oauth/token",
            data=token_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {creds}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            tokens = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.error(f"Notion token exchange failed: {e}")
        return _redirect(f"{FRONTEND_URL}/settings?error=notion_token_failed")

    put_item({
        "PK": f"USER#{user_id}",
        "SK": "INTEGRATION#notion",
        "provider": "notion",
        "access_token": tokens.get("access_token", ""),
        "workspace_name": tokens.get("workspace_name", ""),
        "workspace_id": tokens.get("workspace_id", ""),
        "bot_id": tokens.get("bot_id", ""),
        "status": "connected",
        "connected_at": now_iso(),
    })

    return _redirect(f"{FRONTEND_URL}/settings?connected=notion")


# ──────────────────────────────────────────────
# List / Disconnect Integrations
# ──────────────────────────────────────────────

def list_integrations(event, user_id):
    items = query_pk(f"USER#{user_id}", sk_prefix="INTEGRATION#")
    integrations = []
    for item in items:
        integrations.append({
            "provider": item.get("provider", ""),
            "status": item.get("status", "disconnected"),
            "connected_at": item.get("connected_at"),
            "workspace_name": item.get("workspace_name"),
        })
    return response(200, {"integrations": integrations})


def disconnect_integration(event, user_id):
    provider = get_path_param(event, "provider")
    provider_map = {
        "google": "google_calendar",
        "google_calendar": "google_calendar",
        "notion": "notion",
    }
    sk = f"INTEGRATION#{provider_map.get(provider, provider)}"
    delete_item(f"USER#{user_id}", sk)
    return response(200, {"disconnected": provider})


# ──────────────────────────────────────────────
# Google Calendar Sync Worker (called from agents.py)
# ──────────────────────────────────────────────

def _refresh_google_token(user_id, integration):
    expiry_str = integration.get("token_expiry", "")
    if expiry_str:
        try:
            expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) < expiry - timedelta(minutes=5):
                return integration["access_token"]
        except (ValueError, TypeError):
            pass

    refresh_token = integration.get("refresh_token", "")
    if not refresh_token:
        raise ValueError("No refresh token available")

    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")

    token_data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        tokens = json.loads(resp.read().decode("utf-8"))

    new_access = tokens["access_token"]
    expires_in = tokens.get("expires_in", 3600)
    expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

    from shared.db import update_item
    update_item(f"USER#{user_id}", "INTEGRATION#google_calendar", {
        "access_token": new_access,
        "token_expiry": expiry,
    })
    return new_access


def sync_google_calendar_worker(user_id):
    integration = get_item(f"USER#{user_id}", "INTEGRATION#google_calendar")
    if not integration or integration.get("status") != "connected":
        return {"error": "Google Calendar not connected"}

    access_token = _refresh_google_token(user_id, integration)

    now = datetime.now(timezone.utc)
    time_min = now.strftime("%Y-%m-%dT00:00:00Z")
    time_max = (now + timedelta(days=7)).strftime("%Y-%m-%dT23:59:59Z")

    params = urllib.parse.urlencode({
        "timeMin": time_min,
        "timeMax": time_max,
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 250,
    })
    url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events?{params}"

    try:
        events_data = _http_request(url, headers={"Authorization": f"Bearer {access_token}"})
    except Exception as e:
        logger.error(f"Google Calendar API error: {e}")
        return {"error": f"Failed to fetch calendar events: {str(e)}"}

    events = events_data.get("items", [])

    existing_gcal_blocks = query_pk(f"USER#{user_id}", sk_prefix="BLOCK#gcal-")
    existing_ids = {b["SK"].replace("BLOCK#", "") for b in existing_gcal_blocks}

    synced_ids = set()
    synced = 0

    for ev in events:
        start = ev.get("start", {})
        end = ev.get("end", {})

        start_dt = start.get("dateTime", start.get("date", ""))
        end_dt = end.get("dateTime", end.get("date", ""))

        if not start_dt:
            continue

        try:
            if "T" in start_dt:
                s = datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
                e_dt = datetime.fromisoformat(end_dt.replace("Z", "+00:00"))
                event_date = s.strftime("%Y-%m-%d")
                start_time = s.strftime("%H:%M")
                end_time = e_dt.strftime("%H:%M")
            else:
                event_date = start_dt
                start_time = "00:00"
                end_time = "23:59"
        except (ValueError, TypeError):
            continue

        gcal_id = ev.get("id", "")
        block_id = f"gcal-{gcal_id[:24]}" if gcal_id else generate_id()
        synced_ids.add(block_id)

        block = build_time_block(
            user_id,
            block_id=block_id,
            date=event_date,
            start_time=start_time,
            end_time=end_time,
            title=ev.get("summary", "Calendar Event"),
            block_type="calendar_sync",
            locked=True,
            source="google_calendar",
        )
        put_item(block)
        synced += 1

    removed = 0
    for old_id in existing_ids - synced_ids:
        delete_item(f"USER#{user_id}", f"BLOCK#{old_id}")
        removed += 1

    from shared.db import update_item
    update_item(f"USER#{user_id}", "INTEGRATION#google_calendar", {
        "last_synced_at": now_iso(),
        "last_sync_count": synced,
    })

    return {"synced_events": synced, "removed_events": removed, "provider": "google_calendar"}


# ──────────────────────────────────────────────
# Notion Sync Worker (called from agents.py)
# ──────────────────────────────────────────────

def _read_notion_blocks(block_id, headers, depth=0, max_depth=3):
    if depth > max_depth:
        return []
    text_parts = []
    cursor = None
    while True:
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        try:
            blocks_data = _http_request(url, headers=headers)
        except Exception:
            break
        for block in blocks_data.get("results", []):
            btype = block.get("type", "")
            block_content = block.get(btype, {})
            if isinstance(block_content, dict):
                rich_texts = block_content.get("rich_text", [])
                for rt in rich_texts:
                    text_parts.append(rt.get("plain_text", ""))
            if block.get("has_children"):
                child_text = _read_notion_blocks(block["id"], headers, depth + 1, max_depth)
                text_parts.extend(child_text)
        if not blocks_data.get("has_more"):
            break
        cursor = blocks_data.get("next_cursor")
    return text_parts


def sync_notion_worker(user_id):
    integration = get_item(f"USER#{user_id}", "INTEGRATION#notion")
    if not integration or integration.get("status") != "connected":
        return {"error": "Notion not connected"}

    access_token = integration["access_token"]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    all_results = []
    cursor = None
    for _ in range(5):
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        try:
            search_body = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(
                "https://api.notion.com/v1/search",
                data=search_body,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                search_results = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"Notion search error: {e}")
            if not all_results:
                return {"error": f"Failed to search Notion: {str(e)}"}
            break
        all_results.extend(search_results.get("results", []))
        if not search_results.get("has_more"):
            break
        cursor = search_results.get("next_cursor")

    synced = 0

    for item in all_results:
        obj_type = item.get("object", "")
        notion_id = item.get("id", "")

        title = ""
        props = item.get("properties", {})
        for prop_val in props.values():
            if prop_val.get("type") == "title":
                title_parts = prop_val.get("title", [])
                title = "".join(t.get("plain_text", "") for t in title_parts)
                break
        if not title:
            title = f"Notion {obj_type} {notion_id[:8]}"

        content_text = ""
        if obj_type == "page":
            try:
                text_parts = _read_notion_blocks(notion_id, headers)
                content_text = "\n".join(text_parts)
            except Exception as e:
                logger.warning(f"Failed to read Notion page {notion_id}: {e}")
                content_text = f"[Notion page: {title}]"

        doc_id = f"notion-{notion_id[:20]}"
        doc = build_document(
            user_id,
            doc_id=doc_id,
            file_name=f"{title}.md",
            file_type="md",
            s3_key="",
            extracted_text=content_text[:15000] if content_text else title,
            kb_status="indexed",
            is_master=False,
        )
        doc["source"] = "notion"
        doc["notion_id"] = notion_id
        put_item(doc)
        synced += 1

    from shared.db import update_item
    update_item(f"USER#{user_id}", "INTEGRATION#notion", {
        "last_synced_at": now_iso(),
        "last_sync_count": synced,
    })

    return {"synced_pages": synced, "provider": "notion"}
