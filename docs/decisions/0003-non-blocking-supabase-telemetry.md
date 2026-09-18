# ADR-003: Non-Blocking Asynchronous Supabase Telemetry Logging

## Status

Accepted

## Date

2026-09-18

## Context

The competition judge harness measures endpoint latency and expects prompt HTTP 200 responses. At the same time, persistent audit logs of scenarios, LLM interpretations, and hourly dispatch plans are required for observability, UI dashboards, and evaluation.

Connecting synchronously to cloud databases (like Supabase PostgreSQL) introduces network latency (100-500ms) and creates an external point of failure: if Supabase is down, experiences network blips, or has missing/empty API credentials (`""`), the optimization endpoint must not fail or stall.

## Decision

Decouple telemetry logging using FastAPI `BackgroundTasks` executed via `asyncio.to_thread` (`app/db/supabase_client.py`). Wrap all database calls in exception guards that log warnings to server diagnostics without bubbling up to the client response.

## Alternatives Considered

### 1. Synchronous Inline Database Inserts
- **Pros**: Guarantees row is inserted before HTTP response is sent.
- **Cons**: Penalizes every client request with database round-trip latency. Database timeouts fail user requests.
- **Rejected**: Violates the requirement for low-latency response times.

### 2. External Message Broker / Celery Worker
- **Pros**: Highly scalable for enterprise throughput.
- **Cons**: Requires Redis/RabbitMQ infrastructure, extra Docker services, and elevated resource usage.
- **Rejected**: Excessive operational overhead for hackathon deployment requirements.

## Consequences

- The client receives the solved 24-hour plan immediately upon LP completion (<100ms).
- Database network latency, downtime, or unconfigured credentials (`""`, empty strings) do not impact API availability.
- Thread pool execution preserves asyncio event-loop concurrency.
