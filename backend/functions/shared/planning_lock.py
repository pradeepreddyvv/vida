"""Allow one worker decision flow at a time for each workspace."""
from contextlib import contextmanager
import secrets
import time
from shared.db import _get_table

@contextmanager
def agent_lock(user_id, resource=None, lease_seconds=190):
    table = _get_table()
    key = {'PK':f'USER#{user_id}', 'SK':'RESOURCE_LOCK#'+resource if resource else 'AGENT_LOCK'}
    owner = secrets.token_urlsafe(16)
    try:
        table.put_item(Item={**key,'owner':owner,'expires':int(time.time())+int(lease_seconds)}, ConditionExpression='attribute_not_exists(PK) OR expires < :now',ExpressionAttributeValues={':now':int(time.time())})
    except table.meta.client.exceptions.ConditionalCheckFailedException as exc:
        raise ValueError('Vida is already processing a request for your workspace. Wait for it to finish, then try again.') from exc
    try:
        yield
    finally:
        try:
            table.delete_item(Key=key,ConditionExpression='#o = :owner',ExpressionAttributeNames={'#o':'owner'},ExpressionAttributeValues={':owner':owner})
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            pass
