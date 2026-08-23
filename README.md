# ForgeCart

ForgeCart is the deliberately small target system for the RegressionForge demo. It is a real React storefront backed by FastAPI, SQLite, SMTP delivery, an HTTP fulfillment webhook, and OpenTelemetry-compatible local evidence.

The release is selected with `FORGECART_RELEASE=good|broken|fixed`:

- `good` accepts the storefront's `total_cents` checkout contract.
- `broken` validates the same request against a changed `amount_cents` contract and returns a real HTTP 500.
- `fixed` restores backwards compatibility while retaining `amount_cents` support.

The repository is independent from RegressionForge. The top-level RegressionForge Docker Compose file builds and runs it as the regression target.

## Pull-request certification demo

After this repository has a GitHub `origin`, use the two scripts below from a clean `main` checkout:

```bash
./scripts/create-broken-pr.sh
./scripts/create-fixed-pr.sh
```

The broken script opens an intentionally incompatible PR and expects the required `Deployment Certification` check to fail. Do not merge it. The fixed script opens a separate, backward-compatible replacement PR from `main` and expects the same check to pass.

The workflow uses a self-hosted runner so GitHub can drive the local Docker evidence stack. Configure these repository settings before opening the PRs:

- Actions variable `REGRESSIONFORGE_HOME`: absolute path to the local RegressionForge checkout.
- Optional Actions variable `REGRESSIONFORGE_API_URL`: defaults to `http://localhost:4400` when empty.
- Optional Actions variable `REGRESSIONFORGE_DOCKER_CONFIG`: a directory containing a credential-free `config.json` for macOS service runners that cannot open Docker Desktop's keychain helper.
- Actions secret `REGRESSIONFORGE_CI_TOKEN`: the same value configured in RegressionForge's ignored `.env`.

For safety, certification runs only for non-draft branches inside this repository; forked PR code is never executed on the self-hosted machine.

Run `./scripts/create-broken-pr.sh --dry-run` or `./scripts/create-fixed-pr.sh --dry-run` to inspect the exact contract diff without pushing a branch or opening a PR.

Install the Greptile GitHub App for only this repository. The checked-in `greptile.json` enables a status check and re-review whenever the PR receives a new commit. In GitHub branch protection, require both `Deployment Certification` and the Greptile status check before merge.
