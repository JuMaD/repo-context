---
component:
  name: HTTP Retry Client
  does: "Takes a URL and optional config, returns response with automatic retry on transient failures."

  import: "from core.http_client import RetryClient"
  key_methods:
    - "get(url: str, **kwargs) -> Response"
    - "post(url: str, json: dict | None = None, **kwargs) -> Response"

  input:
    type: str
    description: "Target URL, plus optional body/headers via kwargs."
  output:
    type: Response
    description: "Standard requests-style response object."

  depends_on:
    - component: core.logging
      why: "Structured log output for retry attempts and final failures."
    - component: core.metrics
      why: "Emits counters/timers for dashboarding."
      optional: true

  interfaces:
    external_apis:
      - name: "Any HTTP endpoint"
        purpose: "Outbound HTTP calls"
        env_vars: []
---

# HTTP Retry Client

A thin wrapper around `httpx` that adds exponential backoff, circuit breaking on 5xx, and structured logging.

## Quick Start

```python
from core.http_client import RetryClient

client = RetryClient(max_retries=3, backoff_base=0.25)
response = client.get("https://api.example.com/status")
```

## When to Use This vs. Raw `httpx`

Use `RetryClient` whenever the call is **idempotent** (GET, PUT, DELETE) and the remote service has transient failure modes you want to paper over. For POSTs that mutate state, use raw `httpx` directly so you can decide retry semantics per-call.

## Configuration

| Argument | Default | Notes |
|----------|---------|-------|
| `max_retries` | 3 | Set to 0 to disable retries. |
| `backoff_base` | 0.5 | Seconds; delay grows as `backoff_base * 2^attempt`. |
| `retry_on` | `(500, 502, 503, 504)` | Status codes that trigger a retry. |

## Testing

```bash
pytest tests/unit/test_http_client.py -v
```
