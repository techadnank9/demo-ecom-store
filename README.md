# ForgeCart

ForgeCart is the deliberately small target system for the RegressionForge demo. It is a real React storefront backed by FastAPI, SQLite, SMTP delivery, an HTTP fulfillment webhook, and OpenTelemetry-compatible local evidence.

The release is selected with `FORGECART_RELEASE=good|broken|fixed`:

- `good` accepts the storefront's `total_cents` checkout contract.
- `broken` validates the same request against a changed `amount_cents` contract and returns a real HTTP 500.
- `fixed` restores backwards compatibility while retaining `amount_cents` support.

The repository is independent from RegressionForge. The top-level RegressionForge Docker Compose file builds and runs it as the regression target.

