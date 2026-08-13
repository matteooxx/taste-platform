# Taste Platform

Taste Platform records ratings and tags across movies, shows, anime, games,
and music, then produces local recommendations.

The provider-free runtime is `local_api.py`. The CDK stacks and Lambda handlers
are retained as an optional cloud architecture reference.

## Local API

```bash
python3 local_api.py
```

Open <http://127.0.0.1:8090>. Example:

```bash
curl -X POST http://127.0.0.1:8090/api/profile \
  -H 'Content-Type: application/json' \
  -d '{"item_name":"Example Mystery","item_type":"show","rating":5,"tags":["mystery","drama"]}'

curl -X POST http://127.0.0.1:8090/api/recommendations \
  -H 'Content-Type: application/json' \
  -d '{"item_type":"show","limit":3}'
```

Set `TASTE_AUTH_TOKEN` for non-loopback deployments and send it as
`X-Taste-Token`.

## Ollama

Set `TASTE_OLLAMA_URL` and `TASTE_OLLAMA_MODEL`. Chat uses local profile and
candidate data as context; deterministic recommendations remain the fallback.

## Docker or NAS

```bash
mkdir -p runtime
docker compose up --build -d
```

`runtime/taste.db` is private profile data. Keep it outside Git and behind
normal NAS access controls.

## Checks

```bash
python3 -m pytest -q tests
python3 -m compileall -q .
docker compose config
```

For optional CDK work:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cdk synth
```

The account comes from explicit CDK context or `CDK_DEFAULT_ACCOUNT`; no
account, endpoint, Bedrock Agent ID, or alias ID is embedded in this
repository. Cloud deployment is deliberately parameterized: provide
`BedrockAgentId` and `BedrockAgentAliasId` to the compute and streaming stacks,
plus an existing `InvokerRoleArn` to the streaming stack. The template does
not create a long-lived IAM user.

The cloud path is retained for architecture study and requires a separate
security, cost, region, model, and deployment-order review. It is not needed
for local development or NAS use.

## License

This project is available under the [MIT License](LICENSE).
