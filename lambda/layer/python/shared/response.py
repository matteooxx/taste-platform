import json

SECURITY_HEADERS = {
    "Content-Type": "application/json",
    "X-Content-Type-Options": "nosniff",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
}


def success_response(body: dict, status_code: int = 200) -> dict:
    return {
        "statusCode": status_code,
        "headers": SECURITY_HEADERS,
        "body": json.dumps(body),
    }


def error_response(message: str, status_code: int = 500) -> dict:
    return {
        "statusCode": status_code,
        "headers": SECURITY_HEADERS,
        "body": json.dumps({"error": message}),
    }
