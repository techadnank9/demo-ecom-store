#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 broken|fixed [--dry-run]"
}

if [[ $# -lt 1 || ( "$1" != "broken" && "$1" != "fixed" ) ]]; then
  usage
  exit 2
fi

scenario="$1"
shift
dry_run=false
if [[ ${1:-} == "--dry-run" ]]; then
  dry_run=true
  shift
fi
if [[ $# -ne 0 ]]; then
  usage
  exit 2
fi

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
remote="${FORGECART_PR_REMOTE:-origin}"
base_branch="${FORGECART_PR_BASE:-main}"
timestamp="$(date -u +%Y%m%d%H%M%S)"
branch="demo/regression-${scenario}-${timestamp}"
temp_root="$(mktemp -d "${TMPDIR:-/tmp}/forgecart-demo-pr.XXXXXX")"
checkout="$temp_root/checkout"
body_file=""

cleanup() {
  if git -C "$repo_root" worktree list --porcelain | grep -Fq "worktree $checkout"; then
    git -C "$repo_root" worktree remove --force "$checkout" >/dev/null
  fi
  if [[ -n "$body_file" && -f "$body_file" ]]; then
    rm -f "$body_file"
  fi
  rmdir "$temp_root" 2>/dev/null || true
}
trap cleanup EXIT

if [[ "$dry_run" == true ]]; then
  git -C "$repo_root" worktree add --detach "$checkout" HEAD >/dev/null
else
  if [[ -n "$(git -C "$repo_root" status --porcelain)" ]]; then
    echo "ForgeCart has uncommitted changes. Commit or stash them before creating a demo PR." >&2
    exit 1
  fi
  if ! git -C "$repo_root" remote get-url "$remote" >/dev/null 2>&1; then
    echo "Git remote '$remote' is missing. Add the GitHub repository as origin first." >&2
    exit 1
  fi
  if ! command -v gh >/dev/null 2>&1; then
    echo "GitHub CLI (gh) is required." >&2
    exit 1
  fi
  if ! gh auth status >/dev/null 2>&1; then
    echo "Authenticate GitHub CLI with: gh auth login" >&2
    exit 1
  fi
  git -C "$repo_root" fetch "$remote" "$base_branch"
  git -C "$repo_root" worktree add -b "$branch" "$checkout" "$remote/$base_branch" >/dev/null
fi

if [[ "$scenario" == "broken" ]]; then
  cp "$checkout/backend/forgecart/contracts/broken.py" "$checkout/backend/forgecart/contracts/good.py"
  title="demo: introduce incompatible checkout contract"
  commit_message="Demo incompatible checkout contract"
  expected_gate="FAIL"
  description="This intentionally changes the active checkout request from total_cents to amount_cents. The storefront still submits total_cents, so RegressionForge should block this PR with correlated browser, API, side-effect, and SigNoz evidence."
else
  cp "$checkout/backend/forgecart/contracts/fixed.py" "$checkout/backend/forgecart/contracts/good.py"
  title="demo: preserve checkout compatibility"
  commit_message="Demo backward-compatible checkout contract"
  expected_gate="PASS"
  description="This is the safe replacement for the failed demo PR. It accepts both total_cents and amount_cents, so the existing storefront contract and all downstream side effects remain intact."
fi

if git -C "$checkout" diff --quiet -- backend/forgecart/contracts/good.py; then
  echo "The $scenario contract already matches the base branch; no PR is necessary." >&2
  exit 1
fi

if [[ "$dry_run" == true ]]; then
  echo "Dry run only. The proposed $scenario PR diff is:"
  git -C "$checkout" diff -- backend/forgecart/contracts/good.py
  exit 0
fi

git -C "$checkout" add backend/forgecart/contracts/good.py
git -C "$checkout" commit -m "$commit_message" >/dev/null
git -C "$checkout" push --set-upstream "$remote" "$branch"

repo_slug="$(cd "$checkout" && gh repo view --json nameWithOwner --jq .nameWithOwner)"
body_file="$temp_root/pr-body.md"
printf '%s\n' \
  '## RegressionForge demo' \
  '' \
  "$description" \
  '' \
  "Expected deployment certification: **$expected_gate**" \
  '' \
  '- Greptile reviews the changed contract and its callers.' \
  '- GitHub Actions deploys this exact head commit to ForgeCart.' \
  '- RegressionForge returns the evidence-backed deployment gate.' \
  '- Claude-Mem recalls the most recent certified baseline when configured.' \
  > "$body_file"

pr_url="$(gh pr create \
  --repo "$repo_slug" \
  --base "$base_branch" \
  --head "$branch" \
  --title "$title" \
  --body-file "$body_file")"

echo "Created $scenario demo PR: $pr_url"
echo "Expected RegressionForge gate: $expected_gate"
