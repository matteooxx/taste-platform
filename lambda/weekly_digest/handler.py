import json
import logging
import os

import boto3
from shared import get_dynamo_client

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client("bedrock-runtime")
sns = boto3.client("sns")

MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]


def lambda_handler(event, context):
    try:
        table = get_dynamo_client()
        items = _scan_all_items(table)

        profile_text = _build_profile_text(items)
        digest = _generate_digest(profile_text)

        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="Your Weekly Taste Digest",
            Message=digest,
        )

        logger.info(f"Digest sent successfully, {len(items)} items processed")
        return {"statusCode": 200, "body": "Digest sent"}

    except Exception as e:
        logger.error(f"Weekly digest failed: {e}")
        raise


def _scan_all_items(table) -> list[dict]:
    """Paginated scan to retrieve all items."""
    items = []
    response = table.scan()
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    return items


def _build_profile_text(items: list[dict]) -> str:
    by_category: dict[str, list] = {}
    for item in items:
        cat = item.get("item_type", item.get("category", "general"))
        by_category.setdefault(cat, []).append(item)

    lines = []
    for category, entries in by_category.items():
        lines.append(f"\n## {category.title()}")
        for entry in entries[:20]:
            name = entry.get("item_name", entry.get("title", "unknown"))
            rating = f" ({entry['rating']}/5)" if entry.get("rating") else ""
            lines.append(f"- {name}{rating}")
    return "\n".join(lines)


def _generate_digest(profile_text: str) -> str:
    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Based on this taste profile, write a short weekly digest "
                        "with 3-5 new recommendations across categories. Be concise "
                        "and enthusiastic. Do not include any personal information.\n\n"
                        f"Profile:\n{profile_text}"
                    ),
                }
            ],
        }),
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]
