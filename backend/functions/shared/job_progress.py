"""Persist factual preparation stages; never represent model reasoning as progress."""
from contextvars import ContextVar
from contextlib import contextmanager
from datetime import datetime
import time
from shared.db import update_item
from shared.utils import now_iso

_current = ContextVar('vida_job_progress', default=None)

@contextmanager
def tracking(user_id, job_id):
    token = _current.set((user_id, job_id))
    try:
        yield
    finally:
        _current.reset(token)

def stage(label):
    current = _current.get()
    if current:
        user_id, job_id = current
        update_item(f'USER#{user_id}', f'JOB#{job_id}', {'stage':label, 'updated_at':now_iso()})

def public_job(item):
    status = item.get('status', 'pending')
    deadline = item.get('deadline')
    if not deadline and status in ('pending', 'processing'):
        try:
            started = datetime.fromisoformat(item.get('created_at', '').replace('Z', '+00:00')).timestamp()
            deadline = started + (600 if status == 'pending' else 105)
        except ValueError:
            pass
    expired = status in ('pending','processing') and deadline and time.time() > float(deadline)
    return {'job_id':item['SK'].removeprefix('JOB#'), 'job_type':item.get('job_type'),
            'created_at':item.get('created_at'), 'status':'failed' if expired else status,
            'stage':item.get('stage', 'Waiting to start'),
            'error':'This request stopped before finishing. Check saved proposals and results before trying again.' if expired else item.get('error_message'),
            **({'result':item.get('result',{})} if status == 'completed' else {})}
