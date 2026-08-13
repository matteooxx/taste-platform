import os
import boto3
from boto3.dynamodb.conditions import Key

_table = None


def get_dynamo_client():
    global _table
    if _table is None:
        dynamodb = boto3.resource("dynamodb")
        _table = dynamodb.Table(os.environ["TABLE_NAME"])
    return _table


def get_item(user_id: str, item_id: str) -> dict | None:
    table = get_dynamo_client()
    response = table.get_item(Key={"user_id": user_id, "item_id": item_id})
    return response.get("Item")


def put_item(item: dict) -> None:
    table = get_dynamo_client()
    table.put_item(Item=item)


def query_items(user_id: str, prefix: str | None = None) -> list[dict]:
    table = get_dynamo_client()
    key_condition = Key("user_id").eq(user_id)
    if prefix:
        key_condition = key_condition & Key("item_id").begins_with(prefix)
    response = table.query(KeyConditionExpression=key_condition)
    return response.get("Items", [])
