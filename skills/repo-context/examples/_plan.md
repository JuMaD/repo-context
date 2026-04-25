---
plan:
  name: "HTTP Client v2"
  for: "core/http_client"
  type: architecture
  status: active
  last_updated: 2026-01-15
  focus: "Replace per-call retry config with a typed policy object. Unblock the metrics integration."
  streams:
    - name: "Policy object API"
      priority: now
      status: in_progress
      tasks: 4
      done: 2
    - name: "Metrics sink wiring"
      priority: next
      status: not_started
      blocked_by: "Policy object API"
    - name: "Drop legacy `retry_on` kwarg"
      priority: later
      status: not_started
  questions:
    - "Should policy objects be immutable, or support builder-style mutation?"
  decisions:
    - decision: "Use `tenacity` under the hood rather than rolling our own retry loop."
      date: 2025-12-10
      context: "Avoids re-implementing jitter and circuit-breaking logic."
---

# HTTP Client v2

## Current Focus

Land the `RetryPolicy` type and migrate the two in-tree callers.

## Next

Plumb `core.metrics` counters through once the API stabilizes — currently blocked by the policy refactor since counter labels depend on final public surface.

## Later

Delete the `retry_on` kwarg after one release cycle.
