# Security Policy

## Supported Version

Security fixes are applied to the current `main` branch only. The optional AWS
CDK stacks under `stacks/` and `lambda/` are retained as an architecture
reference and are not supported as a deployment.

## Reporting

Do not open a public issue for a suspected vulnerability. Use the repository's
private vulnerability reporting ("Report a vulnerability" under the Security
tab). Include the affected commit, reproduction steps, impact, and any
suggested mitigation.

## Deployment Boundary

`local_api.py` is a single-user local service. It binds to `127.0.0.1:8090` by
default and is not designed to be exposed to the public internet. When
`TASTE_AUTH_TOKEN` is empty, the API does not authenticate requests.

Before binding it to any non-loopback address:

- set a long, random `TASTE_AUTH_TOKEN`; clients send it as `X-Taste-Token`;
- place the service behind a firewall or an authenticated HTTPS reverse proxy;
- keep `runtime/` and any populated `local.env` readable only by the service
  account, with files at mode `0600`;
- back up `runtime/taste.db` and treat it as private profile history.

## Existing Controls

- optional shared-token authentication through `X-Taste-Token`, compared in
  constant time;
- a loopback-only default bind in both `local_api.py` and `compose.yaml`;
- a reference container that runs as a non-root user with a read-only root
  filesystem, all Linux capabilities dropped, `no-new-privileges`, and a
  `noexec` temporary filesystem;
- CI that runs the test suite, `pip-audit`, and an image build on every push
  and pull request.

## Secret and Data Handling

Never commit or attach:

- `.env`, `local.env`, or any other populated environment file; only
  `local.env.example` is tracked;
- `runtime/`, `taste.db`, or any other SQLite file;
- exports of ratings, profile, recommendation, or chat history;
- cloud credentials, CDK output (`cdk.out/`), deployment endpoints, or
  resource identifiers.

## Local Model Privacy

When `TASTE_OLLAMA_URL` is set, chat requests send local profile and candidate
data to that Ollama endpoint as context. Point it only at a model server you
control. With it unset, recommendations are computed locally from
`local_catalog.json` and the stored profile.
