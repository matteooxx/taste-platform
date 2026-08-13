import json
import logging
import os
import re
import uuid

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock_agent = boto3.client("bedrock-agent-runtime")

AGENT_ID = os.environ["BEDROCK_AGENT_ID"]
AGENT_ALIAS_ID = os.environ["BEDROCK_AGENT_ALIAS_ID"]
MAX_MESSAGE_LENGTH = 4096
SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{2,100}$")

SECURITY_HEADERS = {
    "Content-Type": "application/json",
    "X-Content-Type-Options": "nosniff",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Amz-Security-Token",
}


def lambda_handler(event, context):
    body_str = event.get("body", "{}")
    if event.get("isBase64Encoded"):
        import base64
        body_str = base64.b64decode(body_str).decode("utf-8")

    try:
        body = json.loads(body_str)
    except json.JSONDecodeError:
        return _error("Invalid JSON body", 400)

    message = body.get("message", "").strip()
    if not message:
        return _error("Message is required", 400)
    if len(message) > MAX_MESSAGE_LENGTH:
        return _error(f"Message exceeds {MAX_MESSAGE_LENGTH} characters", 400)

    session_id = body.get("session_id", "")
    if not session_id or not SESSION_ID_PATTERN.match(session_id):
        session_id = str(uuid.uuid4())

    try:
        response = bedrock_agent.invoke_agent(
            agentId=AGENT_ID,
            agentAliasId=AGENT_ALIAS_ID,
            sessionId=session_id,
            inputText=message,
        )

        completion = ""
        for event_chunk in response.get("completion", []):
            if "chunk" in event_chunk:
                chunk_bytes = event_chunk["chunk"].get("bytes", b"")
                if isinstance(chunk_bytes, bytes):
                    completion += chunk_bytes.decode("utf-8")
                else:
                    completion += str(chunk_bytes)

        return {
            "statusCode": 200,
            "headers": SECURITY_HEADERS,
            "body": json.dumps({
                "response": completion,
                "session_id": session_id,
            }),
        }

    except Exception as e:
        logger.error(f"Agent invocation failed: {e}")
        return _error("An internal error occurred", 500)


def _error(message: str, status_code: int) -> dict:
    return {
        "statusCode": status_code,
        "headers": SECURITY_HEADERS,
        "body": json.dumps({"error": message}),
    }
