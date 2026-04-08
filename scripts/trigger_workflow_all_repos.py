#!/usr/bin/env python3
"""
Trigger a GitHub Actions workflow file across repositories in an organization.

This script is designed for use by `.github/workflows/trigger-all-repos.yml`.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import requests


GITHUB_API = "https://api.github.com"


@dataclass
class RepoResult:
    repo: str
    has_workflow: bool
    dispatched: bool
    message: str


class GithubApiError(RuntimeError):
    """Raised for non-recoverable GitHub API errors."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trigger a workflow file across organization repositories."
    )
    parser.add_argument("org", help="GitHub organization name (for example: P4X-ng)")
    parser.add_argument(
        "workflow_file",
        help="Workflow filename in each target repo (for example: workflows-sync.yml)",
    )
    parser.add_argument(
        "--ref",
        default="main",
        help="Git reference (branch/tag/SHA) to dispatch from. Default: main",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Include archived repositories in the scan.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only report workflow presence; do not dispatch.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between repo API calls in seconds. Default: 1.0",
    )
    parser.add_argument(
        "--token-env",
        default="GITHUB_TOKEN",
        help="Environment variable containing the GitHub token. Default: GITHUB_TOKEN",
    )
    return parser.parse_args()


def build_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "opsechat-trigger-all-repos-script",
        }
    )
    return session


def get_json(session: requests.Session, url: str) -> Tuple[int, Dict]:
    response = session.get(url, timeout=30)
    data = {}
    if response.text:
        try:
            data = response.json()
        except ValueError:
            data = {"raw_text": response.text}
    return response.status_code, data


def post_json(session: requests.Session, url: str, body: Dict) -> Tuple[int, Dict]:
    response = session.post(url, json=body, timeout=30)
    data = {}
    if response.text:
        try:
            data = response.json()
        except ValueError:
            data = {"raw_text": response.text}
    return response.status_code, data


def list_org_repositories(
    session: requests.Session, org: str, include_archived: bool
) -> List[str]:
    repos: List[str] = []
    page = 1
    while True:
        url = f"{GITHUB_API}/orgs/{org}/repos?type=all&per_page=100&page={page}"
        status_code, payload = get_json(session, url)
        if status_code != 200:
            message = payload.get("message", "Unknown API error")
            raise GithubApiError(
                f"Failed to list repositories for org '{org}': "
                f"{status_code} {message}"
            )

        if not payload:
            break

        for repo_data in payload:
            if repo_data.get("disabled"):
                continue
            if repo_data.get("archived") and not include_archived:
                continue
            name = repo_data.get("name")
            if name:
                repos.append(name)
        page += 1

    return repos


def check_workflow_exists(
    session: requests.Session, org: str, repo: str, workflow_file: str
) -> Tuple[bool, str]:
    url = f"{GITHUB_API}/repos/{org}/{repo}/actions/workflows/{workflow_file}"
    status_code, payload = get_json(session, url)
    if status_code == 200:
        return True, "Workflow exists"
    if status_code == 404:
        return False, "Workflow file not found"
    message = payload.get("message", "Unexpected API response")
    return False, f"Workflow lookup failed: {status_code} {message}"


def dispatch_workflow(
    session: requests.Session, org: str, repo: str, workflow_file: str, ref: str
) -> Tuple[bool, str]:
    url = f"{GITHUB_API}/repos/{org}/{repo}/actions/workflows/{workflow_file}/dispatches"
    status_code, payload = post_json(session, url, {"ref": ref})
    if status_code == 204:
        return True, "Dispatched"
    message = payload.get("message", "Unexpected API response")
    return False, f"Dispatch failed: {status_code} {message}"


def run(args: argparse.Namespace) -> int:
    token = os.environ.get(args.token_env, "").strip()
    if not token:
        print(
            f"ERROR: Missing token in environment variable '{args.token_env}'.",
            file=sys.stderr,
        )
        return 2

    session = build_session(token)
    try:
        repos = list_org_repositories(session, args.org, args.include_archived)
    except GithubApiError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Organization: {args.org}")
    print(f"Workflow file: {args.workflow_file}")
    print(f"Reference: {args.ref}")
    print(f"Check only: {args.check_only}")
    print(f"Include archived: {args.include_archived}")
    print(f"Repository count: {len(repos)}")
    print("")

    results: List[RepoResult] = []
    for index, repo in enumerate(repos, start=1):
        print(f"[{index}/{len(repos)}] {repo} ...", flush=True)
        has_workflow, message = check_workflow_exists(
            session, args.org, repo, args.workflow_file
        )

        if not has_workflow:
            results.append(
                RepoResult(
                    repo=repo,
                    has_workflow=False,
                    dispatched=False,
                    message=message,
                )
            )
            print(f"  -> {message}")
            time.sleep(max(0.0, args.delay))
            continue

        if args.check_only:
            results.append(
                RepoResult(
                    repo=repo,
                    has_workflow=True,
                    dispatched=False,
                    message="Workflow available (check-only mode)",
                )
            )
            print("  -> Workflow available (check-only mode)")
            time.sleep(max(0.0, args.delay))
            continue

        dispatched, dispatch_message = dispatch_workflow(
            session, args.org, repo, args.workflow_file, args.ref
        )
        results.append(
            RepoResult(
                repo=repo,
                has_workflow=True,
                dispatched=dispatched,
                message=dispatch_message,
            )
        )
        print(f"  -> {dispatch_message}")
        time.sleep(max(0.0, args.delay))

    return print_summary(results, args.check_only)


def print_summary(results: Iterable[RepoResult], check_only: bool) -> int:
    all_results = list(results)
    total = len(all_results)
    with_workflow = sum(1 for r in all_results if r.has_workflow)
    without_workflow = sum(1 for r in all_results if not r.has_workflow)
    dispatched_ok = sum(1 for r in all_results if r.dispatched)
    dispatch_failed = sum(
        1 for r in all_results if r.has_workflow and not r.dispatched and not check_only
    )
    lookup_errors = sum(
        1
        for r in all_results
        if (not r.has_workflow and r.message.startswith("Workflow lookup failed:"))
    )

    print("\nSummary")
    print("-------")
    print(f"Total repositories scanned: {total}")
    print(f"Repositories with workflow: {with_workflow}")
    print(f"Repositories without workflow: {without_workflow}")
    if check_only:
        print("Dispatch mode: check-only (no dispatches attempted)")
    else:
        print(f"Successful dispatches: {dispatched_ok}")
        print(f"Failed dispatches: {dispatch_failed}")
    print(f"Workflow lookup errors: {lookup_errors}")

    if lookup_errors:
        print("\nRepositories with workflow lookup errors:")
        for result in all_results:
            if result.message.startswith("Workflow lookup failed:"):
                print(f"- {result.repo}: {result.message}")

    if not check_only and dispatch_failed:
        print("\nRepositories with dispatch failures:")
        for result in all_results:
            if result.has_workflow and not result.dispatched:
                print(f"- {result.repo}: {result.message}")

    if lookup_errors or dispatch_failed:
        return 1
    return 0


def main() -> int:
    args = parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
