# ADR-002: Deterministic Guardrails Firewall Between LLM and LP Solver

## Status

Accepted

## Date

2026-09-18

## Context

Operator notes arrive as unstructured natural language (e.g., *"Reduce solar to 20% between 1 PM and 3 PM"* or conversational noise like *"The cafeteria menu changed today"*). While modern LLMs are effective at semantic extraction, external LLM outputs cannot be trusted directly inside mathematical solvers:
- An LLM may extract an hour out of bounds (e.g., hour 24 or 25).
- An LLM may produce inverted or duplicate hour ranges.
- An LLM may output a negative solar factor or negative battery reserve exceeding actual battery capacity.
- Unsanitized parameters injected into the HiGHS constraint matrices cause `linprog` infeasibility or unboundedness crashes.

## Decision

Introduce an explicit, deterministic **Guardrails Layer** (`app/optimizer/guardrails.py`) between the LLM interpreter and the LP solver. The guardrails engine validates, sorts, clamps, and sanitizes all directive parameters against system physical invariants before matrix generation.

## Alternatives Considered

### 1. Direct LLM-to-Solver Pipeline
- **Pros**: Fewer layers of abstraction.
- **Cons**: A single hallucinated parameter (e.g., `minimum_energy_kwh = 300` on a 200 kWh battery) crashes the solver and causes HTTP 500 responses to the judge harness.
- **Rejected**: Violates the zero-trust principle for generative AI integration.

### 2. Pydantic-Only Validation
- **Pros**: Standard schema validation at the HTTP boundary.
- **Cons**: Pydantic validates data types, but cannot resolve domain-specific semantic recovery (e.g., clamping out-of-bounds hours to 0..23, converting irrelevant notes to harmless `no_op` entries, or normalizing start-inclusive / end-exclusive intervals).
- **Rejected**: Domain guardrails must sanitize and recover gracefully rather than failing hard on benign prompt edge cases.

## Consequences

- If an operator note is irrelevant distractor text, it is normalized to `applies = False` and `directive_type = "no_op"`.
- All hour indices are deduplicated, bounded to $[0, 23]$, and sorted ascending.
- Solar reduction factors are clamped strictly to $[0.0, 1.0]$.
- Minimum battery reserves are clamped between $0.0$ and `battery.capacity_kwh`.
- The solver is guaranteed to receive mathematically sound constraint vectors.
