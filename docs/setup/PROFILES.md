# OpSecChat Deployment Profiles

OpSecChat ships with one alpha profile and a set of off-by-default
"extended" route groups for features that are out of alpha scope (see
[`../ALPHA_SCOPE.md`](../ALPHA_SCOPE.md)).

This page is the flag reference. For the user-friendly setup walkthrough,
see [`../../QUICKSTART.md`](../../QUICKSTART.md). For the dry install
matrix, see [`INSTALL.md`](INSTALL.md).

---

## 1. Default (alpha) profile

No flags set. The app exposes:

- Closed-roster chat (`/chat`, `/chat/room/...`, `/chat/dm/...`)
- Operator console (`/`, `/console`, `/console/api`, `/dashboard`)
- Operational endpoints (`/health`, `/version`, `/chat/stats`)
- Key-management shell (`/keys`)

Recommended for every alpha deployment.

---

## 2. Extended profile flags

Set per-request via environment variables before starting the app.
Leaving any of these unset keeps the corresponding routes unregistered.

| Variable                              | Effect when set to `1`                                                          |
|---------------------------------------|---------------------------------------------------------------------------------|
| `OPSECHAT_ENABLE_EXTENDED_SERVICES`   | Implicit on for `LEGACY_CHAT`, `EMAIL_STACK`, `HTTP_MAIL` (see below)           |
| `OPSECHAT_ENABLE_LEGACY_CHAT`         | Registers the legacy `/<secret-path>/...` drop-chat (`chat_routes.py`)          |
| `OPSECHAT_ENABLE_EMAIL_STACK`         | Registers the SMTP/IMAP / burner / domain-rotation routes (`email_routes.py`)   |
| `OPSECHAT_ENABLE_HTTP_MAIL`           | Registers the HTTP-mail routes (`http_mail_routes.py`)                          |
| `OPSECHAT_ENABLE_REVIEWS`             | Registers the product-review routes (`review_routes.py`)                        |

All five default to off. They are out of alpha scope. Treat them as
beta-track features and do not enable them in an alpha deployment.

Example (developer-only, for poking at the email stack):

```bash
export OPSECHAT_ENABLE_EXTENDED_SERVICES=1
python bin/runserver.py test
```

---

## 3. Tor enforcement flags

| Variable                       | Effect when set                                                                            |
|--------------------------------|--------------------------------------------------------------------------------------------|
| `OPSECHAT_REQUIRE_TOR`         | Refuse to start unless a hidden service can be published                                   |
| `OPSECHAT_FORCE_TOR_EGRESS`    | Route outbound HTTP / SMTP / IMAP through the Tor SOCKS proxy                              |

The compose stack sets both flags by default. The ad-hoc CLI honours
`OPSECHAT_REQUIRE_TOR=1` by automatically promoting itself to `--tor`
mode if you forgot to pass the flag.

---

## 4. Retention windows

| Variable                  | Default | Effect                                          |
|---------------------------|---------|-------------------------------------------------|
| `MESSAGE_EXPIRY_SECONDS`  | 180     | Per-message TTL                                 |
| `DM_EXPIRY_SECONDS`       | 60      | One-shot DM TTL                                 |
| `ROOM_INACTIVE_SECONDS`   | 3600    | Room TTL after last activity                    |

Lowering these is safe; raising them widens the in-memory data window.
Per-room overrides are not yet supported (alpha gap; see
[`../ALPHA_SCOPE.md`](../ALPHA_SCOPE.md)).

---

## 5. Other operational flags

| Variable                          | Default | Effect                                                            |
|-----------------------------------|---------|-------------------------------------------------------------------|
| `OPSECHAT_SECRET_KEY`             | random  | Flask session secret. Set to a stable value if you need stable session cookies across restarts. |
| `OPSECHAT_TOR_STARTUP_TIMEOUT`    | 30      | Seconds to wait for the Tor control port at boot                  |
| `OPSECHAT_TOR_RETRY_DELAY`        | 1       | Seconds between Tor control retries                               |
| `OPSECHAT_LOG_FILE`               | unset   | If set, structured logs are also written to this file path        |

---

## 6. Worked examples

### Pure alpha hosted operator (compose)

```bash
./compose-up.sh
```

(All Tor enforcement flags are baked into `container-compose.yml`.)

### Pure alpha self-hosted ad-hoc

```bash
python bin/chat-room.py --tor
```

### Developer test mode (no Tor, all alpha endpoints, port 5001)

```bash
python bin/runserver.py test
```

### Out-of-alpha exploration of the HTTP mail stack only

```bash
export OPSECHAT_ENABLE_HTTP_MAIL=1
python bin/runserver.py test
```

This is for development of beta features. Do not ship a deployment with
extended flags set unless you know what you are signing up for.
