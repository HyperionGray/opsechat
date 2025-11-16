# Repository Guidelines

## Project Structure & Module Organization
- `runserver.py`: single Flask + Stem service (Tor setup, chat state, routes). Add helpers near the existing functions.
- `templates/`: Jinja views; keep script and no-script variants (`drop.html`, `drop.noscript.html`, `chats*.html`) aligned so Tor Browser users can opt out of JavaScript.
- `static/`: vendored JS (jQuery, OpenPGP) and simple assets. Replace files in place and avoid build tools.
- Docs (`README.md`, `PGP_USAGE.md`, `PGP_TEST_EXAMPLE.md`, `SECURITY.md`, `MODERNIZATION.md`) capture ops, crypto, and hardening notes—update them whenever behavior changes.
- Packaging files (`requirements.txt`, `setup.py`, `MANIFEST.in`) must mirror any new runtime dependency or asset you add.

## Build, Test, and Development Commands
- `python3 -m venv .venv && source .venv/bin/activate` — isolate Python and Stem.
- `pip install -r requirements.txt` — install Flask + Stem; ensure Tor Browser or a tor daemon exposes ControlPort 9051.
- `TOR_CONTROL_PORT=9051 python runserver.py` — launch the ephemeral onion chat; the console prints the `<service>.onion/<path>` share link.
- `FLASK_DEBUG=1 python runserver.py` — optional hot reload for local tweaking; disable before sharing the service.

## Coding Style & Naming Conventions
- Follow PEP 8, 4-space indents, and snake_case. Group imports stdlib/third-party/local like `runserver.py`.
- Keep routes thin: sanitize input once, preserve the PGP passthrough, and move shared logic into helpers.
- Templates stay lowercase-with-dashes, minimal JS, and compatible with NoScript. Prefer vanilla JS or the bundled jQuery.

## Testing Guidelines
- `tests/` houses the pytest helpers suite covering ID generation, message wrapping, and expiry logic; extend it as new modules arrive. Run with `PYTHONPATH=. pytest`.
- Manual smoke test: start the server, open `http://127.0.0.1:5000/<path>` for noscript and `<path>/yesscript` for JS, then confirm Tor clients reach the printed onion URL.
- For PGP changes, follow `PGP_TEST_EXAMPLE.md` to craft fixtures and confirm encrypted payloads bypass sanitization.

## Commit & Pull Request Guidelines
- Use short, imperative commit subjects (“Add PGP test example documentation”) and wrap bodies at 72 characters.
- PRs should describe motivation, Tor/PGP impact, linked issues, and the tests or manual steps performed; include screenshots when templates change.
- Separate commits for docs, backend, and assets so reviewers can audit the security-sensitive areas quickly.

## Security & Configuration Tips
- Review `SECURITY.md` before touching crypto, logging, or dependencies, and mention mitigations in the PR body.
- Never commit onion hostnames, Tor credentials, or local `.tor` directories; rely on environment variables such as `TOR_CONTROL_PORT`.
- When upgrading static assets (especially `static/jquery.js`), manually verify both NoScript and script-enabled flows.
