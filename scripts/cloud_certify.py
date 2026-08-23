#!/usr/bin/env python3
"""Deploy the exact PR SHA to Render, then block GitHub on RegressionForge."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


RENDER_API = "https://api.render.com/v1"
DEPLOY_FAILURES = {"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"}
TERMINAL_RUNS = {"PASSED", "FAILED", "NEEDS_REVIEW", "ERROR"}


def request_json(
    url: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    bearer: str = "",
    timeout: int = 30,
) -> tuple[int, dict | list]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"accept": "application/json"}
    if body is not None:
        headers["content-type"] = "application/json"
    if bearer:
        headers["authorization"] = f"Bearer {bearer}"
    request = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as error:
        detail = error.read().decode(errors="replace")[:1200]
        raise RuntimeError(f"{method} {url} returned HTTP {error.code}: {detail}") from error
    except (URLError, OSError) as error:
        reason = getattr(error, "reason", str(error))
        raise RuntimeError(f"Could not reach {url}: {reason}") from error


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"GitHub Actions variable or secret {name} is required")
    return value


def public_url(name: str) -> str:
    value = required_env(name).rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError(f"{name} must be a public https:// URL")
    return value


def render_request(path: str, *, method: str = "GET", body: dict | None = None) -> tuple[int, dict | list]:
    return request_json(
        f"{RENDER_API}{path}",
        method=method,
        body=body,
        bearer=required_env("RENDER_API_KEY"),
    )


def _deploy_objects(payload: dict | list) -> list[dict]:
    values = payload if isinstance(payload, list) else payload.get("deploys", [])
    return [
        value.get("deploy", value)
        for value in values
        if isinstance(value, dict) and isinstance(value.get("deploy", value), dict)
    ]


def trigger_deploy(service_id: str, commit_sha: str) -> str:
    status, payload = render_request(
        f"/services/{service_id}/deploys",
        method="POST",
        body={"commitId": commit_sha, "clearCache": "do_not_clear"},
    )
    if isinstance(payload, dict) and payload.get("id"):
        return str(payload["id"])
    if status != 202:
        raise RuntimeError(f"Render did not return a deploy ID for {service_id}")

    for _ in range(30):
        _, listed = render_request(f"/services/{service_id}/deploys?limit=20")
        for deploy in _deploy_objects(listed):
            if deploy.get("commit", {}).get("id") == commit_sha and deploy.get("id"):
                return str(deploy["id"])
        time.sleep(2)
    raise RuntimeError(f"Timed out finding the queued Render deploy for {service_id}")


def wait_for_deploy(service_id: str, deploy_id: str, commit_sha: str, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        _, payload = render_request(f"/services/{service_id}/deploys/{deploy_id}")
        if not isinstance(payload, dict):
            raise RuntimeError(f"Render returned an invalid deploy response for {service_id}")
        status = str(payload.get("status", "unknown"))
        if status != last:
            print(f"Render {service_id}: {status}")
            last = status
        deployed_commit = payload.get("commit", {}).get("id", "")
        if deployed_commit and deployed_commit != commit_sha:
            raise RuntimeError(
                f"Render deploy {deploy_id} resolved {deployed_commit[:12]}, expected {commit_sha[:12]}"
            )
        if status == "live":
            return
        if status in DEPLOY_FAILURES:
            raise RuntimeError(f"Render deploy {deploy_id} ended in {status}")
        time.sleep(5)
    raise RuntimeError(f"Render deploy {deploy_id} did not become live within {timeout} seconds")


def wait_for_json_health(url: str, commit_sha: str = "", attempts: int = 90) -> dict:
    last_error = "not contacted"
    for _ in range(attempts):
        try:
            _, body = request_json(url)
            if isinstance(body, dict) and body.get("status") == "ok":
                deployed = str(body.get("render_git_commit", ""))
                if commit_sha and deployed != commit_sha:
                    last_error = f"health reports commit {deployed[:12] or 'missing'}"
                else:
                    return body
        except RuntimeError as error:
            last_error = str(error)
        time.sleep(3)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def wait_for_web(url: str, attempts: int = 90) -> None:
    last_error = "not contacted"
    for _ in range(attempts):
        try:
            request = Request(url, headers={"user-agent": "RegressionForge-CI/1.0"})
            with urlopen(request, timeout=15) as response:
                if 200 <= response.status < 400:
                    return
        except (HTTPError, URLError, OSError) as error:
            last_error = str(error)
        time.sleep(3)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def changed_files(source: Path, base_sha: str, head_sha: str) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(source), "diff", "--name-only", f"{base_sha}...{head_sha}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "Could not calculate the pull-request diff")
    return [line for line in completed.stdout.splitlines() if line][:100]


def append_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT", "")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def write_summary(run: dict, evidence_url: str, commit_sha: str) -> None:
    gate = (run.get("gate") or {}).get("status", "UNKNOWN")
    reason = (run.get("gate") or {}).get("reason", "Certification returned no gate reason")
    failed = [
        result.get("step_name", result.get("step_id", "Unknown step"))
        for result in run.get("step_results", [])
        if result.get("status") in {"FAILED", "ERROR", "NEEDS_REVIEW"}
    ]
    lines = [
        "## RegressionForge cloud deployment certification",
        "",
        f"**Gate:** `{gate}`  ",
        f"**Commit deployed:** `{commit_sha}`  ",
        f"**Run:** `{run.get('id', 'unknown')}`  ",
        f"**Reason:** {reason}  ",
        f"**Evidence room:** [Open same-run evidence]({evidence_url})",
    ]
    if failed:
        lines.extend(["", "**Non-passing checks:**", *[f"- {name}" for name in failed]])
    summary = "\n".join(lines) + "\n"
    summary_path = os.getenv("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as output:
            output.write(summary)
    print(summary)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--pr-url", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--default-branch", default="main")
    parser.add_argument("--deploy-timeout", type=int, default=1200)
    parser.add_argument("--run-timeout", type=int, default=900)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        raise RuntimeError("--repository must use owner/repository format")
    if not re.fullmatch(r"[0-9a-f]{40}", args.head_sha):
        raise RuntimeError("--head-sha must be a full Git SHA")

    api_service = required_env("RENDER_FORGECART_API_SERVICE_ID")
    web_service = required_env("RENDER_FORGECART_WEB_SERVICE_ID")
    forge_api = public_url("REGRESSIONFORGE_API_URL")
    storefront = public_url("FORGECART_STOREFRONT_URL")
    store_api = public_url("FORGECART_API_URL")
    ci_token = required_env("REGRESSIONFORGE_CI_TOKEN")

    wait_for_json_health(f"{forge_api}/health", attempts=20)
    print(f"Deploying exact PR commit {args.head_sha[:12]} to both ForgeCart services")
    api_deploy = trigger_deploy(api_service, args.head_sha)
    web_deploy = trigger_deploy(web_service, args.head_sha)
    wait_for_deploy(api_service, api_deploy, args.head_sha, args.deploy_timeout)
    wait_for_deploy(web_service, web_deploy, args.head_sha, args.deploy_timeout)

    wait_for_json_health(f"{store_api}/health", args.head_sha)
    wait_for_web(storefront)

    version = f"pr-{args.pr_number}-{args.head_sha[:8]}"
    files = changed_files(args.source_dir, args.base_sha, args.head_sha)
    _, queued = request_json(
        f"{forge_api}/api/ci/certifications",
        method="POST",
        bearer=ci_token,
        body={
            "project_id": "prj_forgecart",
            "environment": "pull-request",
            "version": version,
            "commit_sha": args.head_sha,
            "storefront_url": storefront,
            "api_url": store_api,
            "repository": args.repository,
            "repository_provider": "github",
            "default_branch": args.default_branch,
            "pull_request_number": args.pr_number,
            "pull_request_url": args.pr_url,
            "base_sha": args.base_sha,
            "head_sha": args.head_sha,
            "changed_files": files,
        },
    )
    if not isinstance(queued, dict) or not queued.get("run_id"):
        raise RuntimeError("RegressionForge did not return a run ID")
    run_id = str(queued["run_id"])
    evidence_url = str(queued["evidence_room_url"])
    append_output("run-id", run_id)
    append_output("evidence-room-url", evidence_url)
    print(f"RegressionForge certification queued: {run_id}")

    deadline = time.monotonic() + args.run_timeout
    last = ""
    while time.monotonic() < deadline:
        _, run = request_json(f"{forge_api}/api/runs/{run_id}")
        if not isinstance(run, dict):
            raise RuntimeError("RegressionForge returned an invalid run response")
        status = str(run.get("status", "UNKNOWN"))
        if status != last:
            print(f"RegressionForge: {status}")
            last = status
        if status in TERMINAL_RUNS and run.get("gate"):
            gate = str(run["gate"]["status"])
            append_output("gate", gate)
            write_summary(run, evidence_url, args.head_sha)
            return 0 if gate == "PASS" else 1
        time.sleep(3)
    raise RuntimeError(f"Certification {run_id} did not finish within {args.run_timeout} seconds")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
