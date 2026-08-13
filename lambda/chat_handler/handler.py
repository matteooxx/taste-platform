import json
import logging
import os
import re

import boto3
from shared import success_response, error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock_agent = boto3.client("bedrock-agent-runtime")

AGENT_ID = os.environ["BEDROCK_AGENT_ID"]
AGENT_ALIAS_ID = os.environ["BEDROCK_AGENT_ALIAS_ID"]
MAX_MESSAGE_LENGTH = 4096
SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{2,100}$")


def lambda_handler(event, context):
    if event.get("rawPath") == "/health":
        return success_response({"status": "healthy"})

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return error_response("Invalid JSON body", 400)

    message = body.get("message", "").strip()
    if not message:
        return error_response("Message is required", 400)
    if len(message) > MAX_MESSAGE_LENGTH:
        return error_response(f"Message exceeds {MAX_MESSAGE_LENGTH} characters", 400)

    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    user_sub = claims.get("sub", "default_user")

    session_id = body.get("session_id") or user_sub
    if not SESSION_ID_PATTERN.match(session_id):
        session_id = user_sub

    try:
        completion = _invoke_agent(session_id, message)
    except bedrock_agent.exceptions.ClientError as e:
        if "ConflictException" in str(type(e)):
            session_id = f"{user_sub}-{context.aws_request_id[:8]}"
            completion = _invoke_agent(session_id, message)
        else:
            logger.error(f"Bedrock agent error: {e}")
            return error_response("Failed to process message", 502)
    except Exception as e:
        logger.error(f"Unexpected error invoking agent: {e}")
        return error_response("An internal error occurred", 500)

    return success_response({
        "response": completion,
        "session_id": session_id,
    })


def _invoke_agent(session_id: str, input_text: str) -> str:
    response = bedrock_agent.invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=AGENT_ALIAS_ID,
        sessionId=session_id,
        inputText=input_text,
    )

    completion = ""
    for event_chunk in response.get("completion", []):
        if "chunk" in event_chunk:
            chunk_bytes = event_chunk["chunk"].get("bytes", b"")
            if isinstance(chunk_bytes, bytes):
                completion += chunk_bytes.decode("utf-8")
            else:
                completion += str(chunk_bytes)

    return completion
