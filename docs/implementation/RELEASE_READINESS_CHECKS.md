# Release Readiness Checks

This document describes the automated release-readiness checker added for repository hygiene and pre-release confidence.

## Purpose

The checker validates three practical release gates:

1. Required release artifacts exist (for example `README.md`, `VERSION`, `requirements.txt`, `Pfyfile.pf`).
2. Source files do not contain unfinished implementation markers (`TODO`, `FIXME`, `STUB`, `HACK`, `XXX`, `TBD`).
3. The repository does not contain stale backup/reject files (for example `*~HEAD`, `*.orig`, `*.rej`, `*.bak`).

These checks catch common "last mile" issues before packaging or deployment.

## Script Location

- `scripts/release_readiness_check.py`

## Local Usage

Run directly:

```bash
python3 scripts/release_readiness_check.py
```

Machine-readable output:

```bash
python3 scripts/release_readiness_check.py --json
```

## PF Task Integration

The PF test task now includes release-readiness checks by default:

```bash
python3 pf-tasks/test.py
```

Run only release-readiness checks:

```bash
python3 pf-tasks/test.py --release-readiness-only
```

Skip readiness checks in environments where you only want deployment checks:

```bash
python3 pf-tasks/test.py --skip-release-readiness
```

## Test Coverage

Unit tests for the checker live in:

- `tests/test_release_readiness_check.py`

The tests cover:
- Missing required paths detection
- Source TODO marker detection
- Non-source file exclusion from marker checks
- Stale backup artifact detection
