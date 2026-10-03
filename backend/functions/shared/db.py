import os
import json
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key

_table = None


def _get_table():
    global _table
    if _table is None:
        dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("REGION", "us-east-2"))
        _table = dynamodb.Table(os.environ.get("TABLE_NAME", "vida-main"))
    return _table


def get_item(pk, sk):
    resp = _get_table().get_item(Key={"PK": pk, "SK": sk}, ConsistentRead=True)
    return resp.get("Item")


def normalize(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value


def put_item(item):
    _get_table().put_item(Item=normalize(item))


def delete_item(pk, sk):
    _get_table().delete_item(Key={"PK": pk, "SK": sk})


def update_item(pk, sk, updates):
    expr_parts = []
    names = {}
    values = {}
    for i, (k, v) in enumerate(updates.items()):
        alias = f"#k{i}"
        val_alias = f":v{i}"
        expr_parts.append(f"{alias} = {val_alias}")
        names[alias] = k
        values[val_alias] = v

    _get_table().update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET " + ", ".join(expr_parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=normalize(values),
    )


def query_pk(pk, sk_prefix=None, limit=100, scan_forward=True, consistent=False):
    table = _get_table()
    kwargs = {
        "KeyConditionExpression": Key("PK").eq(pk),
        "Limit": limit,
        "ScanIndexForward": scan_forward,
        "ConsistentRead": consistent,
    }
    if sk_prefix:
        kwargs["KeyConditionExpression"] = kwargs["KeyConditionExpression"] & Key("SK").begins_with(sk_prefix)

    items = []
    while True:
        resp = table.query(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp or len(items) >= limit:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    return items[:limit]


def query_gsi(index_name, pk_value, sk_prefix=None, limit=100, scan_forward=True):
    table = _get_table()
    pk_attr = f"{index_name}PK"
    sk_attr = f"{index_name}SK"

    kce = Key(pk_attr).eq(pk_value)
    if sk_prefix:
        kce = kce & Key(sk_attr).begins_with(sk_prefix)

    kwargs = {
        "IndexName": index_name,
        "KeyConditionExpression": kce,
        "Limit": limit,
        "ScanIndexForward": scan_forward,
    }

    items = []
    while True:
        resp = table.query(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp or len(items) >= limit:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    return items[:limit]


def batch_write(items):
    table = _get_table()
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=normalize(item))
