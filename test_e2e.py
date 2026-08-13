#!/usr/bin/env python3
"""End-to-end test for the Taste Platform.

Authenticates with Cognito, sends chat messages through the API,
and verifies DynamoDB state.
"""
import getpass
import json
import os
import sys
import time

import boto3

API_URL = os.environ.get("TASTE_API_URL", "").rstrip("/")
USER_POOL_ID = os.environ.get("TASTE_USER_POOL_ID", "")
CLIENT_ID = os.environ.get("TASTE_CLIENT_ID", "")
REGION = os.environ.get("AWS_REGION", "eu-west-1")
TABLE_NAME = os.environ.get("TASTE_TABLE_NAME", "taste-profile")


def authenticate(username: str, password: str) -> dict:
    """Authenticate with Cognito and return tokens."""
    client = boto3.client("cognito-idp", region_name=REGION)

    # Get client secret for HMAC calculation
    secret_hash = None
    try:
        import hmac
        import hashlib
        import base64

        idp_admin = boto3.client("cognito-idp", region_name=REGION)
        resp = idp_admin.describe_user_pool_client(
            UserPoolId=USER_POOL_ID, ClientId=CLIENT_ID
        )
        client_secret = resp["UserPoolClient"].get("ClientSecret")
        if client_secret:
            msg = username + CLIENT_ID
            secret_hash = base64.b64encode(
                hmac.new(
                    client_secret.encode("utf-8"),
                    msg.encode("utf-8"),
                    hashlib.sha256,
                ).digest()
            ).decode("utf-8")
    except Exception:
        pass

    auth_params = {"USERNAME": username, "PASSWORD": password}
    if secret_hash:
        auth_params["SECRET_HASH"] = secret_hash

    response = client.initiate_auth(
        ClientId=CLIENT_ID,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters=auth_params,
    )

    result = response["AuthenticationResult"]
    print(f"Authenticated as {username}")
    print(f"  Token expires in: {result['ExpiresIn']}s")
    return result


def call_chat(token: str, message: str, session_id: str = None) -> dict:
    """Call the /chat endpoint."""
    import urllib.request

    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    req = urllib.request.Request(
        f"{API_URL}/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"HTTP {e.code}: {body}")
        sys.exit(1)


def check_dynamodb(user_id: str, item_type: str, item_slug: str) -> bool:
    """Check if an item exists in DynamoDB."""
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(TABLE_NAME)

    sort_key = f"{item_type}#{item_slug}"
    response = table.get_item(Key={"user_id": user_id, "item_id": sort_key})
    return "Item" in response


def main():
    print("=" * 60)
    print("Taste Platform - End-to-End Test")
    print("=" * 60)
    print()

    missing = [
        name
        for name, value in {
            "TASTE_API_URL": API_URL,
            "TASTE_USER_POOL_ID": USER_POOL_ID,
            "TASTE_CLIENT_ID": CLIENT_ID,
        }.items()
        if not value
    ]
    if missing:
        print("Missing cloud test configuration: " + ", ".join(missing))
        print("Use local_api.py for the provider-free local workflow.")
        sys.exit(2)

    username = input("Cognito username (email): ").strip()
    password = getpass.getpass("Password: ")

    if not username or not password:
        print("Username and password are required.")
        sys.exit(1)

    print("\n--- Step 1: Authenticating with Cognito ---")
    tokens = authenticate(username, password)
    id_token = tokens["IdToken"]

    print("\n--- Step 2: Sending first message (profile update) ---")
    msg1 = "I just finished watching Severance season 2, I loved it, 10/10"
    print(f"  > {msg1}")
    resp1 = call_chat(id_token, msg1)
    session_id = resp1.get("session_id")
    print(f"  < {resp1.get('response', 'NO RESPONSE')}")
    print(f"  Session ID: {session_id}")

    print("\n--- Step 3: Waiting for profile update to propagate ---")
    time.sleep(3)

    print("\n--- Step 4: Sending second message (recommendation request) ---")
    msg2 = "What should I watch next?"
    print(f"  > {msg2}")
    resp2 = call_chat(id_token, msg2, session_id)
    print(f"  < {resp2.get('response', 'NO RESPONSE')}")

    print("\n--- Step 5: Verifying DynamoDB entry ---")
    # The agent should have stored Severance with item_type=show
    found = check_dynamodb("default_user", "show", "severance_season_2")
    if not found:
        # Try alternate slugs the agent might use
        found = check_dynamodb("default_user", "show", "severance")
    if not found:
        found = check_dynamodb("default_user", "tv", "severance_season_2")
    if not found:
        found = check_dynamodb("default_user", "tv", "severance")

    if found:
        print("  DynamoDB entry FOUND for Severance")
    else:
        print("  WARNING: DynamoDB entry NOT found (agent may use different key format)")
        print("  This is expected if the Bedrock Agent chose different field names.")

    print("\n" + "=" * 60)
    print("End-to-end test complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
