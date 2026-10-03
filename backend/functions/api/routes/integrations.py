import json
import logging
import os
import urllib.parse
import urllib.request
import base64
import time
import secrets
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone

from shared.db import get_item, put_item, query_pk, delete_item, _get_table
from shared.utils import response, generate_id, now_iso, today_str, get_query_param, get_path_param, parse_body
from shared.models import build_time_block, build_document

logger = logging.getLogger(__name__)

FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://dieldwu0y5z3o.cloudfront.net").rstrip("/")
CALLBACK_BASE_URL = os.environ.get("CALLBACK_BASE_URL", "https://dieldwu0y5z3o.cloudfront.net").rstrip("/")
GOOGLE_REDIRECT_URI = f"{CALLBACK_BASE_URL}/api/auth/google/callback"
NOTION_REDIRECT_URI = f"{CALLBACK_BASE_URL}/api/auth/notion/callback"

GOOGLE_SCOPES = "https://www.googleapis.com/auth/calendar.calendarlist.readonly https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email"


def _configure_callback(event):
    from shared.oauth_config import load_credentials
    load_credentials()
    global GOOGLE_REDIRECT_URI, NOTION_REDIRECT_URI
    env_base = os.environ.get("CALLBACK_BASE_URL", "").rstrip("/")
    if env_base:
        GOOGLE_REDIRECT_URI = env_base + "/api/auth/google/callback"
        NOTION_REDIRECT_URI = env_base + "/api/auth/notion/callback"
    else:
        domain = event.get("requestContext", {}).get("domainName", "")
        stage = event.get("requestContext", {}).get("stage", "")
        if domain and domain.endswith('.amazonaws.com'):
            base = "https://" + domain + ("/" + stage if stage and stage != "$default" else "")
            GOOGLE_REDIRECT_URI = base + "/api/auth/google/callback"
            NOTION_REDIRECT_URI = base + "/api/auth/notion/callback"


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
    provider = "Notion" if "api.notion.com" in urllib.parse.urlparse(url).netloc else "Google Calendar"
    retry_safe = method == "GET" or url == "https://api.notion.com/v1/search"
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                raw = resp.read().decode("utf-8")
                try:
                    parsed = json.loads(raw)
                    if not isinstance(parsed, dict): raise ValueError("Expected object")
                    return parsed
                except (ValueError, UnicodeError):
                    if attempt == 0 and retry_safe:
                        time.sleep(.5)
                        continue
                    raise ValueError(f"{provider} returned an unreadable response. Please try Sync again; your saved data is unchanged by this response.")
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt == 0 and retry_safe:
                time.sleep(1)
                continue
            if exc.code in (401, 403):
                raise ValueError(f"Reconnect {provider} in Settings and grant access to the calendars or pages you want to use.") from exc
            raise ValueError(f"{provider} could not complete the request (HTTP {exc.code}). Please try again.") from exc


# ──────────────────────────────────────────────
# Google Calendar OAuth
# ──────────────────────────────────────────────

def start_google_auth(event, user_id):
    from shared.demo_workspace import require_personal
    require_personal(user_id)
    _configure_callback(event)
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    if not client_id:
        return response(400, {"error": "Google OAuth not configured"})

    state = secrets.token_urlsafe(32)
    put_item({
        "PK": "OAUTH_STATE",
        "SK": f"STATE#{state}",
        "user_id": user_id,
        "provider": "google",
        "expires_at_epoch": int(time.time()) + 600,
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
    _configure_callback(event)
    code = get_query_param(event, "code", "")
    state = get_query_param(event, "state", "")
    error = get_query_param(event, "error", "")

    if error:
        return _redirect(f"{FRONTEND_URL}/settings?error=google_denied")

    if not code or not state:
        return _redirect(f"{FRONTEND_URL}/settings?error=google_missing_params")

    table = _get_table()
    try:
        state_item = table.delete_item(Key={"PK":"OAUTH_STATE", "SK":f"STATE#{state}"},
            ConditionExpression="#p = :p AND expires_at_epoch > :now",
            ExpressionAttributeNames={"#p":"provider"},
            ExpressionAttributeValues={":p":"google", ":now":int(time.time())},
            ReturnValues="ALL_OLD")["Attributes"]
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return _redirect(f"{FRONTEND_URL}/settings?error=invalid_state")
    user_id = state_item["user_id"]

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
        with urllib.request.urlopen(req, timeout=12) as resp:
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
    from shared.demo_workspace import require_personal
    require_personal(user_id)
    _configure_callback(event)
    client_id = os.environ.get("NOTION_CLIENT_ID", "")
    if not client_id:
        return response(400, {"error": "Notion OAuth not configured"})

    state = secrets.token_urlsafe(32)
    put_item({
        "PK": "OAUTH_STATE",
        "SK": f"STATE#{state}",
        "user_id": user_id,
        "provider": "notion",
        "expires_at_epoch": int(time.time()) + 600,
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
    _configure_callback(event)
    code = get_query_param(event, "code", "")
    state = get_query_param(event, "state", "")
    error = get_query_param(event, "error", "")

    if error:
        return _redirect(f"{FRONTEND_URL}/settings?error=notion_denied")

    if not code or not state:
        return _redirect(f"{FRONTEND_URL}/settings?error=notion_missing_params")

    table = _get_table()
    try:
        state_item = table.delete_item(Key={"PK":"OAUTH_STATE", "SK":f"STATE#{state}"},
            ConditionExpression="#p = :p AND expires_at_epoch > :now",
            ExpressionAttributeNames={"#p":"provider"},
            ExpressionAttributeValues={":p":"notion", ":now":int(time.time())},
            ReturnValues="ALL_OLD")["Attributes"]
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return _redirect(f"{FRONTEND_URL}/settings?error=invalid_state")
    user_id = state_item["user_id"]

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
        with urllib.request.urlopen(req, timeout=12) as resp:
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

    from shared.notion_mirror import request_sync
    request_sync(user_id)
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
            "last_synced_at": item.get("last_synced_at"),
            "last_sync_count": item.get("last_sync_count", 0),
            "sync_status": item.get("sync_status"),
            "selected_calendars": item.get("selected_calendars", []),
            "mirror_status": item.get("mirror_status"),
            "mirror_error": item.get("mirror_error"),
            "mirror_pages": item.get("mirror_pages", {}),
            "mirror_synced_at": item.get("mirror_synced_at"),
        })
    return response(200, {"integrations": integrations})


def list_google_calendars(event, user_id):
    integration = get_item(f"USER#{user_id}", "INTEGRATION#google_calendar") or {}
    if integration.get("status") != "connected": raise ValueError("Connect Google Calendar first.")
    token = _refresh_google_token(user_id, integration)
    calendars, params = [], {"maxResults":250}
    for _ in range(20):
        data = _http_request("https://www.googleapis.com/calendar/v3/users/me/calendarList?" + urllib.parse.urlencode(params), headers={"Authorization":f"Bearer {token}"})
        calendars.extend({"id":c["id"], "title":c.get("summary", "Calendar"), "primary":c.get("primary", False), "access_role":c.get("accessRole", "reader")} for c in data.get("items", []) if not c.get("deleted"))
        if not data.get("nextPageToken"): break
        params["pageToken"] = data["nextPageToken"]
    else: raise ValueError("Too many calendars to list. Please contact support.")
    return response(200, {"calendars":calendars, "selected":integration.get("selected_calendars", [])})


def select_google_calendars(event, user_id):
    selected = parse_body(event).get("calendar_ids", [])
    if not isinstance(selected, list) or not 1 <= len(selected) <= 10 or any(not isinstance(x,str) for x in selected):
        raise ValueError("Choose between 1 and 10 calendars.")
    available = json.loads(list_google_calendars(event,user_id)["body"])["calendars"]
    if not set(selected) <= {c["id"] for c in available}: raise ValueError("Choose only calendars you can access.")
    from shared.db import update_item
    update_item(f"USER#{user_id}", "INTEGRATION#google_calendar", {"selected_calendars":list(dict.fromkeys(selected)), "sync_status":"selection_changed"})
    return response(200, {"selected":selected})


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
    from shared.oauth_config import load_credentials
    load_credentials()
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
    with urllib.request.urlopen(req, timeout=12) as resp:
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


def _serialized_sync(provider):
    from functools import wraps
    def decorate(worker):
        @wraps(worker)
        def run(user_id):
            table = _get_table()
            key = {"PK": f"USER#{user_id}", "SK": f"SYNCLOCK#{provider}"}
            owner = secrets.token_urlsafe(16)
            try:
                table.put_item(Item={**key, "owner":owner, "expires":int(time.time())+300},
                    ConditionExpression="attribute_not_exists(PK) OR expires < :now",
                    ExpressionAttributeValues={":now":int(time.time())})
            except table.meta.client.exceptions.ConditionalCheckFailedException:
                raise ValueError("A sync is already running. Wait for it to finish.")
            try:
                return worker(user_id)
            finally:
                try:
                    table.delete_item(Key=key, ConditionExpression="#o = :owner",
                        ExpressionAttributeNames={"#o":"owner"}, ExpressionAttributeValues={":owner":owner})
                except table.meta.client.exceptions.ConditionalCheckFailedException:
                    pass
        return run
    return decorate


@_serialized_sync("google_calendar")
def sync_google_calendar_worker(user_id):
    from shared.demo_workspace import require_personal
    require_personal(user_id)
    integration = get_item(f"USER#{user_id}", "INTEGRATION#google_calendar")
    if not integration or integration.get("status") != "connected":
        raise ValueError("Google Calendar not connected")
    token = _refresh_google_token(user_id, integration)
    profile = get_item(f"USER#{user_id}", "PROFILE") or {}
    zone = ZoneInfo(profile.get("timezone") or "UTC")
    start = datetime.now(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    params = {"timeMin": start.isoformat(), "timeMax": end.isoformat(), "singleEvents": "true",
              "orderBy": "startTime", "maxResults": 250}
    selected = integration.get("selected_calendars", [])
    if not selected: raise ValueError("Choose your Google calendars in Settings before planning.")
    events = []
    import hashlib
    for calendar_id in selected:
        calendar_params = dict(params)
        for _ in range(20):
            data = _http_request("https://www.googleapis.com/calendar/v3/calendars/" + urllib.parse.quote(calendar_id, safe="") + "/events?" + urllib.parse.urlencode(calendar_params), headers={"Authorization": f"Bearer {token}"})
            for item in data.get("items", []):
                item["_calendar_id"] = calendar_id
                events.append(item)
            if not data.get("nextPageToken"): break
            calendar_params["pageToken"] = data["nextPageToken"]
        else: raise ValueError("Calendar exceeds this sync batch; no events were changed")
    existing = query_pk(f"USER#{user_id}", sk_prefix="BLOCK#gcal-", limit=10000)
    in_window = {b['SK']: b for b in existing if start.date().isoformat() <= b.get('date', '') < end.date().isoformat()}
    desired = {}
    for ev in events:
        if ev.get('status') == 'cancelled' or ev.get('transparency') == 'transparent':
            continue
        if ev.get('attendees') and any(a.get('self') and a.get('responseStatus') == 'declined' for a in ev['attendees']):
            continue
        first, last = ev.get('start', {}), ev.get('end', {})
        if first.get('dateTime'):
            begin = datetime.fromisoformat(first['dateTime'].replace('Z', '+00:00')).astimezone(zone)
            finish = datetime.fromisoformat(last['dateTime'].replace('Z', '+00:00')).astimezone(zone)
        elif first.get('date'):
            begin = datetime.fromisoformat(first['date']).replace(tzinfo=zone)
            finish = datetime.fromisoformat(last['date']).replace(tzinfo=zone)
        else:
            continue
        cursor = max(begin, start)
        finish = min(finish, end)
        while cursor < finish:
            midnight = (cursor + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            segment_end = min(finish, midnight)
            date = cursor.date().isoformat()
            block = build_time_block(user_id, block_id=f"gcal-{hashlib.sha256(ev['_calendar_id'].encode()).hexdigest()[:12]}-{ev['id']}-{date}", date=date,
                    start_time=cursor.strftime('%H:%M'), end_time='24:00' if segment_end == midnight else segment_end.strftime('%H:%M'),
                    title=ev.get('summary', 'Busy'), block_type='busy', locked=True, source='google_calendar')
            block['google_event_id'] = ev['id']
            block['google_calendar_id'] = ev['_calendar_id']
            block['source_updated_at'] = ev.get('updated')
            desired[block['SK']] = block
            cursor = segment_end
    changed_dates = set()
    fields = ('date', 'start_time', 'end_time', 'title', 'google_event_id')
    for sk, block in desired.items():
        old = in_window.get(sk)
        if not old or any(old.get(k) != block.get(k) for k in fields):
            put_item(block)
            changed_dates.add(block['date'])
    removed = 0
    for sk, old in in_window.items():
        if sk not in desired:
            delete_item(f"USER#{user_id}", sk)
            changed_dates.add(old['date']); removed += 1
    from shared.db import update_item
    update_item(f"USER#{user_id}", "INTEGRATION#google_calendar", {
        "last_synced_at": now_iso(), "last_sync_count": len(desired), "sync_status": "complete", "synced_from":start.date().isoformat(), "synced_until":end.date().isoformat()})
    return {"synced_events": len(desired), "removed_events": removed, "affected_dates": sorted(changed_dates),
            "provider": "google_calendar", "scope": "Selected calendars, next 7 days"}


def create_google_event(user_id, title, date, start_time, end_time, description="", calendar_id=None):
    integration = get_item(f"USER#{user_id}", "INTEGRATION#google_calendar")
    if not integration or integration.get("status") != "connected":
        return {"error": "Google Calendar not connected"}

    access_token = _refresh_google_token(user_id, integration)

    start_dt = f"{date}T{start_time}:00"
    end_dt = f"{date}T{end_time}:00"

    tz = "America/Los_Angeles"
    profile = get_item(f"USER#{user_id}", "PROFILE")
    if profile:
        tz = profile.get("timezone") or tz

    if not calendar_id or calendar_id not in integration.get("selected_calendars", []):
        return {"error":"Choose a selected calendar before creating an event."}

    event_body = {
        "summary": title,
        "start": {"dateTime": start_dt, "timeZone": tz},
        "end": {"dateTime": end_dt, "timeZone": tz},
    }
    if description:
        event_body["description"] = description

    try:
        result = _http_request(
            "https://www.googleapis.com/calendar/v3/calendars/" + urllib.parse.quote(calendar_id, safe="") + "/events",
            data=event_body,
            headers={"Authorization": f"Bearer {access_token}"},
            method="POST",
        )
        return {"created": True, "event_id": result.get("id"), "title": title, "date": date, "start_time": start_time, "end_time": end_time}
    except Exception as e:
        return {"error": f"Failed to create event: {str(e)}"}


def _event_calendar(user_id, event_id):
    matches = {b.get('google_calendar_id', 'primary') for b in query_pk(f'USER#{user_id}', 'BLOCK#gcal-', limit=10000) if b.get('google_event_id') == event_id}
    if len(matches) != 1: raise ValueError('Sync your calendar and choose one unambiguous event before changing it.')
    return urllib.parse.quote(next(iter(matches)), safe='')


def update_google_event(user_id, event_id, updates):
    integration = get_item(f"USER#{user_id}", "INTEGRATION#google_calendar")
    if not integration or integration.get("status") != "connected":
        return {"error": "Google Calendar not connected"}

    access_token = _refresh_google_token(user_id, integration)

    tz = "America/Los_Angeles"
    profile = get_item(f"USER#{user_id}", "PROFILE")
    if profile:
        tz = profile.get("timezone") or tz

    patch_body = {}
    if "title" in updates:
        patch_body["summary"] = updates["title"]
    if "description" in updates:
        patch_body["description"] = updates["description"]
    if "date" in updates and "start_time" in updates:
        patch_body["start"] = {"dateTime": f"{updates['date']}T{updates['start_time']}:00", "timeZone": tz}
    if "date" in updates and "end_time" in updates:
        patch_body["end"] = {"dateTime": f"{updates['date']}T{updates['end_time']}:00", "timeZone": tz}

    try:
        result = _http_request(
            f"https://www.googleapis.com/calendar/v3/calendars/{_event_calendar(user_id, event_id)}/events/{urllib.parse.quote(event_id, safe='')}",
            data=patch_body,
            headers={"Authorization": f"Bearer {access_token}"},
            method="PATCH",
        )
        return {"updated": True, "event_id": event_id, "changes": updates}
    except Exception as e:
        return {"error": f"Failed to update event: {str(e)}"}


def delete_google_event(user_id, event_id):
    integration = get_item(f"USER#{user_id}", "INTEGRATION#google_calendar")
    if not integration or integration.get("status") != "connected":
        return {"error": "Google Calendar not connected"}

    access_token = _refresh_google_token(user_id, integration)

    try:
        req = urllib.request.Request(
            f"https://www.googleapis.com/calendar/v3/calendars/{_event_calendar(user_id, event_id)}/events/{urllib.parse.quote(event_id, safe='')}",
            headers={"Authorization": f"Bearer {access_token}"},
            method="DELETE",
        )
        with urllib.request.urlopen(req, timeout=12):
            pass
        return {"deleted": True, "event_id": event_id}
    except Exception as e:
        return {"error": f"Failed to delete event: {str(e)}"}


# ──────────────────────────────────────────────
# Notion Sync Worker (called from agents.py)
# ──────────────────────────────────────────────

@_serialized_sync("notion")
def sync_notion_worker(user_id):
    from shared.demo_workspace import require_personal
    require_personal(user_id)
    """Checkpoint a bounded sync batch; the client can resume with another async job."""
    integration = get_item(f"USER#{user_id}", "INTEGRATION#notion")
    if not integration or integration.get('status') != 'connected':
        raise ValueError('Notion not connected')
    headers = {"Authorization": f"Bearer {integration['access_token']}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    pk = f"USER#{user_id}"
    state = get_item(pk, 'SYNC#notion') or {'PK': pk, 'SK': 'SYNC#notion', 'pages': [], 'search_done': False,
              'cursor': None, 'current': None, 'synced': 0, 'started_at': now_iso()}
    deadline = time.monotonic() + 45
    calls = 0
    while calls < 15 and time.monotonic() < deadline:
        current = state.get('current')
        if current:
            if current['blocks']:
                block = current['blocks'][0]
                params = {'page_size':100}
                if block.get('cursor'): params['start_cursor'] = block['cursor']
                time.sleep(.35)
                data = _http_request(f"https://api.notion.com/v1/blocks/{block['id']}/children?" + urllib.parse.urlencode(params), headers=headers)
                calls += 1
                children = []
                for child in data.get('results', []):
                    kind = child.get('type', '')
                    content = child.get(kind, {})
                    text = ''.join(t.get('plain_text', '') for t in content.get('rich_text', []))
                    current['text'] += text + '\n'
                    if child.get('has_children'):
                        children.append({'id':child['id']})
                if len(current['text'].encode('utf-8')) > 200000:
                    raise ValueError('A Notion page exceeds the 200 KB text limit; choose smaller pages')
                if data.get('has_more') and data.get('next_cursor'):
                    block['cursor'] = data['next_cursor']
                else:
                    current['blocks'].pop(0)
                current['blocks'].extend(children)
                put_item(state)
                continue
            page = current['page']
            doc = build_document(user_id, doc_id='notion-' + page['id'], file_name=page['title'], file_type='md',
                                 extracted_text=current['text'], kb_status='indexed')
            doc.update(source='notion', notion_id=page['id'], source_updated_at=page.get('updated'))
            put_item(doc)
            state['synced'] += 1; state['current'] = None
            put_item(state)
            continue
        if state['pages']:
            page = state['pages'].pop(0)
            state['current'] = {'page': page, 'blocks': [{'id':page['id']}], 'text':''}
            continue
        if state['search_done']:
            from shared.db import update_item
            update_item(pk, 'INTEGRATION#notion', {'last_synced_at':now_iso(), 'last_sync_count':state['synced'], 'sync_status':'complete'})
            delete_item(pk, 'SYNC#notion')
            return {'synced_pages': state['synced'], 'provider':'notion', 'partial':False}
        body = {'page_size': 50, 'filter': {'value':'page', 'property':'object'}}
        if state.get('cursor'): body['start_cursor'] = state['cursor']
        data = _http_request('https://api.notion.com/v1/search', data=body, headers=headers, method='POST')
        calls += 1
        for page in data.get('results', []):
            if page.get('archived') or page.get('in_trash'):
                continue
            title = next((''.join(t.get('plain_text','') for t in prop.get('title', []))
                          for prop in page.get('properties', {}).values() if prop.get('type') == 'title'), 'Untitled page')
            state['pages'].append({'id':page['id'], 'title':title, 'updated':page.get('last_edited_time')})
        state['cursor'] = data.get('next_cursor')
        state['search_done'] = not data.get('has_more')
        put_item(state)
    put_item(state)
    from shared.db import update_item
    update_item(pk, 'INTEGRATION#notion', {'sync_status':'partial', 'last_sync_count':state['synced']})
    return {'synced_pages':state['synced'], 'provider':'notion', 'partial':True,
            'message':'More pages remain. Continue sync to resume this batch.'}
