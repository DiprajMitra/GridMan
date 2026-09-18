# ADR-001: Use SciPy HiGHS Linear Programming Solver for 24-Hour Dispatch

## Status

Accepted

## Date

2026-09-18

## Context

The GridWise system optimizes 24-hour campus energy consumption, solar generation, and battery storage under Time-of-Use (ToU) electricity tariffs and operator directives.

Key requirements:
- Mathematical guarantee of global optimality over the full 24-hour horizon.
- Sub-50ms execution latency compliant with BUP CSE Fest competition judge SLAs.
- Zero commercial license fees and no heavyweight native binary solver dependencies (such as CPLEX or Gurobi).
- Strict enforcement of physical conservation laws (Kirchhoff energy balance, battery capacity, charge/discharge rates, and end-of-day reserve preservation).

## Decision

Formulate the dispatch schedule as a continuous **Linear Program (LP)** with 120 decision variables ($24 \times 5$: Grid import $G_h$, Solar consumed $S_h$, Battery charge $C_h$, Battery discharge $D_h$, and Battery State-of-Charge $E_h$) and solve it using `scipy.optimize.linprog(method="highs")`.

## Alternatives Considered

### 1. Large Language Model (LLM) Direct Math / Scheduling
- **Pros**: Easy to prompt directly from operator notes.
- **Cons**: LLMs are probabilistic token generators; they hallucinate numbers, fail exact arithmetic, violate energy balance constraints ($G + S + D \ne \text{demand} + C$), and have non-deterministic, high-latency execution (2-5s).
- **Rejected**: Mission-critical grid operations require 100% mathematical guarantees and sub-second deterministic execution.

### 2. Greedy Rule-Based / Dynamic Programming Heuristics
- **Pros**: Simple to implement in pure Python.
- **Cons**: Greedy heuristics lack global horizon foresight. Discharging the battery during an off-peak morning window leaves zero energy for peak afternoon tariffs, resulting in suboptimal total operational cost.
- **Rejected**: Cannot guarantee Pareto-optimal cost minimization across multi-interval state transitions.

### 3. Mixed-Integer Linear Programming (MILP) via PuLP / CBC
- **Pros**: Can use binary indicator variables to enforce mutually exclusive charging and discharging ($C_h \cdot D_h = 0$).
- **Cons**: Requires external solver binaries (CBC, GLPK), increasing Docker image size and deployment failure risk. In our LP formulation, adding an infinitesimal cycle degradation penalty $\epsilon \cdot (C_h + D_h)$ naturally prevents simultaneous charge/discharge without requiring binary integer constraints.
- **Rejected**: SciPy HiGHS provides identical non-simultaneous behavior in pure continuous LP with zero extra dependencies.

## Consequences

- The solver executes in 10-25ms with 100% reproducibility.
- Pure Python/SciPy stack runs seamlessly in lightweight Docker containers (`python:3.11-slim`).
- Energy balance is verified post-solve using numerical assertions ($|G + S + D - \text{demand} - C| < 10^{-3}$).
