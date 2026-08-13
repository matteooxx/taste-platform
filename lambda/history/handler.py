import json
import logging
from decimal import Decimal

from shared import query_items, success_response, error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o == int(o) else float(o)
        return super().default(o)


def lambda_handler(event, context):
    """Returns the user's full taste profile for the frontend to display."""
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    user_id = claims.get("sub", "default_user")

    params = event.get("queryStringParameters") or {}
    item_type = params.get("type")
    prefix = f"{item_type}#" if item_type else None

    try:
        items = query_items(user_id, prefix)
    except Exception as e:
        logger.error(f"DynamoDB query failed: {e}")
        return error_response("Failed to retrieve history", 500)

    result = []
    for item in items:
        result.append({
            "item_name": item.get("item_name", item.get("title", "")),
            "item_type": item.get("item_type", item.get("category", "")),
            "rating": int(item["rating"]) if item.get("rating") else None,
            "notes": item.get("notes", ""),
            "updated_at": int(item["updated_at"]) if item.get("updated_at") else None,
        })

    result.sort(key=lambda x: x.get("updated_at") or 0, reverse=True)

    body = json.loads(json.dumps({"items": result, "count": len(result)}, cls=DecimalEncoder))
    return success_response(body)
