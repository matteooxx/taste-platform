# AI Handbook: Taste Platform

Read this file before changing the project.

## Status And Scope

This personal project is a technically public-ready snapshot. It contains two
separate paths:

- `local_api.py`: supported provider-free runtime using SQLite
- `app.py`, `stacks/`, `lambda/`: optional historical AWS CDK architecture

Normal development and NAS operation must not require the cloud path.

## No-Cloud Runtime

```bash
python3 local_api.py
```

The API binds to <http://127.0.0.1:8090>, stores data in
`runtime/taste.db`, and exposes health, profile, history, recommendations, and
chat endpoints. Recommendations use `local_catalog.json` plus profile ratings
and tags.

Set `TASTE_OLLAMA_URL` and `TASTE_OLLAMA_MODEL` for a local model. If the model
is absent or fails, deterministic recommendations remain available.

Docker/NAS:

```bash
mkdir -p runtime
docker compose up --build -d
```

Before binding to a LAN address, set a strong `TASTE_AUTH_TOKEN`; clients send
it as `X-Taste-Token`. Protect the port with a firewall or authenticated
reverse proxy. Treat the SQLite database as private profile history.

### Amazon Replacement Map

| Optional cloud component | PC/NAS replacement |
| --- | --- |
| API Gateway and Lambda | `local_api.py` or the Docker service |
| DynamoDB | SQLite at `runtime/taste.db` |
| Bedrock Agent/model | deterministic scoring or local Ollama |
| Cognito | `X-Taste-Token` on trusted local clients |
| Secrets Manager/KMS | mode-`0600` local environment file and host storage controls |
| EventBridge/SNS digest | host cron/systemd timer plus local mail or notification tooling |

## Cloud Reference

The CDK account is resolved from explicit context or `CDK_DEFAULT_ACCOUNT`;
none is embedded in source. Agent and alias IDs are CloudFormation parameters,
and the streaming path accepts an existing role ARN instead of creating an IAM
user. `cdk synth` is a local check, but deployment creates chargeable resources
and permissions. Review stack IAM, model IDs, regions, cost, retention,
deployment order, and deletion policy before any deployment.

`test_e2e.py` is cloud-only and requires `TASTE_API_URL`,
`TASTE_USER_POOL_ID`, `TASTE_CLIENT_ID`, `TASTE_TABLE_NAME`, and an explicitly
selected profile. Do not run it against an unknown deployment.

## Checks

```bash
python3 -m pytest -q tests
python3 -m compileall -q .
docker compose config
cdk synth
```

Inspect synthesized IAM and resource replacement whenever a stack changes.

## Data And Publication Rules

Never commit `.env`, cloud credentials, user-pool secrets, tokens, profile
history, chat history, local databases, CDK output, deployment endpoints, or
resource identifiers. Verify model/service claims against current official
documentation.

Publish only sanitized `main` after tests and tree/history secret scans. Update
this handbook after local API, scoring, catalog, data model, CDK, or deployment
changes.
