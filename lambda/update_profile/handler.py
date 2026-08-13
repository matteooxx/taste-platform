import logging
import re
import time

from shared import put_item

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALLOWED_TYPES = {"movie", "show", "anime", "game", "music"}
MAX_NAME_LENGTH = 200


def lambda_handler(event, context):
    params = event.get("parameters", [])
    param_map = {p["name"]: p["value"] for p in params}

    user_id = param_map.get("user_id", "default_user")
    item_type = param_map.get("item_type", "general")
    item_name = param_map.get("item_name", "")
    rating = param_map.get("rating")
    notes = param_map.get("notes", "")

    if item_type not in ALLOWED_TYPES:
        return _agent_response(event, f"Invalid item_type: {item_type}. Must be one of: {', '.join(ALLOWED_TYPES)}")

    if not item_name or len(item_name) > MAX_NAME_LENGTH:
        return _agent_response(event, f"item_name is required and must be under {MAX_NAME_LENGTH} characters")

    rating_int = None
    if rating:
        try:
            rating_int = int(rating)
            if not 1 <= rating_int <= 5:
                return _agent_response(event, "Rating must be between 1 and 5")
        except (ValueError, TypeError):
            return _agent_response(event, "Rating must be a valid integer between 1 and 5")

    item_slug = re.sub(r"[^a-z0-9]+", "_", item_name.lower()).strip("_")
    sort_key = f"{item_type}#{item_slug}"

    item = {
        "user_id": user_id,
        "item_id": sort_key,
        "item_name": item_name,
        "item_type": item_type,
        "notes": notes,
        "updated_at": int(time.time()),
    }

    if rating_int:
        item["rating"] = rating_int

    try:
        put_item(item)
    except Exception as e:
        logger.error(f"DynamoDB write failed: {e}")
        return _agent_response(event, "Failed to update profile, please try again")

    return _agent_response(event, f"Profile updated: {item_name} ({item_type}) rated {rating_int}/5")


def _agent_response(event: dict, message: str) -> dict:
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup", ""),
            "function": event.get("function", ""),
            "functionResponse": {
                "responseBody": {
                    "TEXT": {"body": message}
                }
            },
        },
    }
