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

> **`pytest` and `cdk synth` require Node.js on the host, and nothing in the
> project declared it.** The test suite imports `aws-cdk-lib`, which synthesizes
> through JSII and shells out to `node`; on a clean Python runtime all five stack
> test modules fail at collection with
> `FileNotFoundError: [Errno 2] No such file or directory: 'node'`. The code is
> fine - with Node present the same suite reports **17 passed**. Install Node 18
> or newer alongside Python before running the checks. `requirements.txt` cannot
> express this, because it is a system dependency rather than a Python one.
>
> The no-cloud runtime (`local_api.py`) and the Docker service use **only the
> Python standard library** and need no Node at all. Node is required strictly
> for the optional CDK path and for the tests that cover it.

## Disposable Build Verification

Both paths below run in throwaway containers and install nothing on the host,
which is what makes them safe to run on the NAS appliance - it has no `pip`, no
`ensurepip`, and no Node, and package installation on it is forbidden.

**Path A - the project's own container.** Verifies the `Dockerfile`.

```bash
docker build -t taste-platform:throwaway .
docker run -d --rm -p 18090:8090 taste-platform:throwaway
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:18090/health
```

Expected: `200`, and the container log reads
`Taste Platform local API: http://0.0.0.0:8090`. `/`, `/health`,
`/recommendations` and `/catalog` all answer `200`.

**Path B - a clean stock runtime, without this project's Dockerfile.** Verifies
that the dependency manifests and documented checks work on a machine that knows
nothing about the project. This is the path that found the missing Node
prerequisite; Path A cannot find it, because the image contains neither the
tests nor the CDK path.

```bash
docker run --rm -v "$PWD":/src:ro -w /work --tmpfs /work:rw,exec,size=1g \
  node:22-slim sh -c '
    apt-get -qq update && apt-get -qq install -y python3 python3-venv
    cp -r /src/. /work/ && chmod -R u+rwX /work
    python3 -m venv /work/.venv && . /work/.venv/bin/activate
    pip install -q --upgrade pip && pip install -q -r requirements.txt
    python -m compileall -q .
    python -m pytest -q tests'
```

Expected: `17 passed`. The sources are mounted **read-only** and copied to a
tmpfs before anything is installed, so a build cannot modify the archive.

> **Why `COPY --chown` is load-bearing in the Dockerfile.** Every file in this
> archive is stored mode `0660`, with no permission for others. `COPY` preserves
> the build context's permissions, so copying the sources and *then* switching to
> a non-root `USER` produces an image that builds with no error at all and dies
> on startup with `python: can't open file '/app/local_api.py': [Errno 13]
> Permission denied`. The runtime user is therefore created **before** the `COPY`,
> and the `COPY` hands the files over with `--chown=taste:taste`. Keep that order.
> `king-of-meal-prep` has always used this idiom; this project did not, and the
> failure was invisible until the image was actually run.

## Data And Publication Rules

Never commit `.env`, cloud credentials, user-pool secrets, tokens, profile
history, chat history, local databases, CDK output, deployment endpoints, or
resource identifiers. Verify model/service claims against current official
documentation.

Publish only sanitized `main` after tests and tree/history secret scans. Update
this handbook after local API, scoring, catalog, data model, CDK, or deployment
changes.
