import json
import logging
from decimal import Decimal

from shared import query_items

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o == int(o) else float(o)
        return super().default(o)


def lambda_handler(event, context):
    params = event.get("parameters", [])
    param_map = {p["name"]: p["value"] for p in params}

    user_id = param_map.get("user_id", "default_user")
    item_type = param_map.get("item_type")
    limit = min(int(param_map.get("limit", "20")), 50)

    prefix = f"{item_type}#" if item_type else None

    try:
        items = query_items(user_id, prefix)
    except Exception as e:
        logger.error(f"DynamoDB query failed: {e}")
        return _agent_response(event, json.dumps({"error": "Failed to retrieve profile"}))

    high_rated = [i for i in items if i.get("rating") and int(i["rating"]) >= 4]
    high_rated.sort(key=lambda x: int(x.get("rating", 0)), reverse=True)
    high_rated = high_rated[:limit]

    profile_context = {
        "total_items": len(items),
        "top_rated": [
            {
                "item_name": i.get("item_name", i.get("title", "")),
                "item_type": i.get("item_type", i.get("category", "")),
                "rating": int(i.get("rating", 0)),
                "notes": i.get("notes", ""),
            }
            for i in high_rated
        ],
    }

    return _agent_response(event, json.dumps(profile_context, cls=DecimalEncoder))


def _agent_response(event: dict, body: str) -> dict:
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup", ""),
            "function": event.get("function", ""),
            "functionResponse": {
                "responseBody": {
                    "TEXT": {"body": body}
                }
            },
        },
    }
