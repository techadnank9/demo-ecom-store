# ForgeCart

ForgeCart is the deliberately small target system for the RegressionForge demo. It is a real React storefront backed by FastAPI, SQLite, SMTP delivery, an HTTP fulfillment webhook, and OpenTelemetry telemetry correlated to each certification run.

The release is selected with `FORGECART_RELEASE=good|broken|fixed`:

- `good` accepts the storefront's `total_cents` checkout contract.
- `broken` validates the same request against a changed `amount_cents` contract and returns a real HTTP 500.
- `fixed` restores backwards compatibility while retaining `amount_cents` support.

The repository is independent from RegressionForge. It can run inside the
top-level RegressionForge Docker Compose stack or as the cloud candidate
deployment described below.

## Pull-request certification demo

From a clean `main` checkout, open the three demo PRs in order:

```bash
./scripts/create-good-pr.sh
./scripts/create-broken-pr.sh
./scripts/create-fixed-pr.sh
```

The good PR makes a harmless contract change and establishes a passing
Claude-Mem baseline. The broken PR changes checkout to require `amount_cents`
and expects `Deployment Certification` to fail; do not merge it. The fixed PR
opens independently from `main`, accepts both field names, and expects the same
workflow to pass. Add `--dry-run` to any script to inspect its exact diff
without pushing a branch or opening a PR.

The workflow uses GitHub-hosted `ubuntu-latest`. It asks Render to deploy the
exact PR head SHA to `forgecart-api` and `forgecart-storefront`, verifies both
live revisions, and starts the hosted RegressionForge gate. Configure these
Actions variables:

- `RENDER_FORGECART_API_SERVICE_ID`
- `RENDER_FORGECART_WEB_SERVICE_ID`
- `REGRESSIONFORGE_API_URL`
- `FORGECART_API_URL`
- `FORGECART_STOREFRONT_URL`

Configure these Actions secrets:

- `RENDER_API_KEY`
- `REGRESSIONFORGE_CI_TOKEN`

Install the Greptile GitHub App for only this repository. The checked-in
`greptile.json` enables its PR review/status behavior. Put the Greptile API key
only on the RegressionForge Render service, not in this repository or its
Actions secrets.

The complete setup order, Render services, exact variables, SigNoz and
Claude-Mem bootstrap, rollback, and cleanup are in the
[RegressionForge cloud guide](https://github.com/KaushikSiva/regression-forge/blob/main/docs/RENDER_CLOUD.md).
