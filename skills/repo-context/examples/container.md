---
container:
  name: Core Libraries
  does: "Reusable, application-agnostic building blocks."
  type: index
  contains:
    - core/http_client
    - core/logging
    - core/metrics
    - core/config
---

# Core Libraries

Everything under `core/` is meant to be importable from any application without pulling in domain knowledge about a specific product.

Rules of thumb:

- `core/` modules MUST NOT import from `applications/` or `infrastructure/`.
- Each module owns its own `README.md` with component frontmatter.
- External API clients (HTTP, DB, vendor SDKs) live here when they're shared; single-use clients stay in their consuming application.

## Current Modules

| Module | Purpose |
|--------|---------|
| `http_client/` | Retrying HTTP client with circuit breaker. |
| `logging/` | Structured logging helpers. |
| `metrics/` | Counter/timer primitives, stdout + Prometheus sinks. |
| `config/` | Pydantic-settings loader for env-driven config. |
