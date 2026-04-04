# Developer Quickstart

## Prerequisites

- Python 3.12+
- Node.js 20+ and npm
- Tor available locally for full runtime testing
- Podman (preferred) or Docker for container validation

## Local setup

```bash
cd /path/to/opsechat

python3 -m venv .venv
source .venv/bin/activate

python3 -m pip install -r requirements.txt
python3 -m pip install -r requirements-dev.txt

npm ci
```

## Fast validation loop

Run the smallest checks first:

```bash
cd /path/to/opsechat

python3 -m pytest tests/test_rate_limit_and_health.py tests/test_container_deployment.py
npx playwright test tests/basic.spec.js
```

These cover:

- `/health` contract and security headers
- container and compose deployment configuration
- basic endpoint smoke checks through the mock server

## Run the app locally

### Without Tor

```bash
cd /path/to/opsechat
python3 runserver.py test
```

Useful checks:

```bash
curl -i http://127.0.0.1:5000/health
curl -i http://127.0.0.1:5000/
```

### With Tor

```bash
cd /path/to/opsechat
python3 runserver.py
```

The server prints the generated `.onion` URL and secret path at startup.

## Container validation

```bash
cd /path/to/opsechat
./compose-up.sh
./compose-down.sh
```

`./compose-up.sh` now performs readiness checks before returning:

- verifies `opsechat-tor` readiness
- verifies `opsechat-app` readiness
- verifies the app container serves `http://127.0.0.1:5000/health`

The application container includes a `/health` healthcheck, and compose probes the same endpoint.

## Full test commands already in the repo

```bash
cd /path/to/opsechat

python3 -m pytest
npx playwright test
python3 pf-tasks/test.py --skip-e2e
```

## Files to know

- `runserver.py` - main runtime entrypoint
- `app_factory.py` - Flask app creation and route registration
- `monitoring.py` - `/health` payload generation
- `docker-compose.yml` - local container deployment
- `Dockerfile` - container build and app healthcheck
- `tests/test_rate_limit_and_health.py` - health endpoint and security header coverage
- `tests/test_container_deployment.py` - deployment safety checks
- `tests/basic.spec.js` - lightweight Playwright smoke tests

## Maintenance checklist

- Keep `/health` stable and lightweight; deployment checks rely on it.
- When changing runtime wiring, update `tests/basic.spec.js`.
- When changing container behavior, update `tests/test_container_deployment.py`.
- Re-run Python tests and the basic Playwright smoke test before pushing.
- Review `SECURITY.md`, `README.md`, and this file when setup or deployment steps change.
