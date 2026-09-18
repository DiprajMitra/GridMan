# System Design Philosophy: GridWise

> **Core Ideology**: Architectural integrity, deterministic mathematical guarantees, and fault-tolerant decoupling for mission-critical microgrid optimization.

---

## 1. The Separation of Fuzzy NLP and Deterministic Math

### The Anti-Pattern: LLM-as-a-Solver
A common failure mode in modern AI applications is asking Large Language Models to perform numerical optimization, schedule dispatch, or arithmetic calculations. Generative language models are probabilistic token predictors:
- They lack numerical precision.
- They cannot guarantee constraint satisfaction (e.g., Kirchhoff's current laws, energy balance, battery capacity limits).
- They produce nondeterministic, irreproducible results.

### The GridWise Principle: LLM as an Interface, Solver as an Oracle
In GridWise, the LLM is strictly confined to **linguistic intent extraction**:
$$\text{Natural Language Notes} \xrightarrow{\text{LLM / Fallback Parser}} \text{Structured JSON Directives} \xrightarrow{\text{Guardrails}} \mathbf{A}, \mathbf{b}, \mathbf{c} \xrightarrow{\text{HiGHS LP}} \text{Optimal Schedule}$$

The solver (SciPy HiGHS) is an exact mathematical oracle. It provides mathematical guarantees of feasibility and global optimality in milliseconds, completely immune to prompt drift or token sampling randomness.

---

## 2. Zero-Trust Guardrails as a Secure Boundary

External LLM outputs are treated as untrusted user input:
- **Never pass raw LLM outputs to numerical solvers.**
- If an LLM misinterprets an hour window as `[24, 25]` or extracts a negative battery reserve, naive solvers will raise infeasibility exceptions or crash.
- **The Guardrails Engine** sanitizes, clamps, deduplicates, and validates all directive parameters against physical system specifications.
- **Fail-Safe Recovery**: If a directive is irreparably malformed, the guardrail neutralizes it to a harmless `no_op` with `applies = False`, preserving overall service continuity rather than failing the entire request.

---

## 3. Global Foresight vs. Greedy Heuristics

A simple greedy heuristic might discharge the battery immediately whenever demand exceeds solar. However, microgrid economics under Time-of-Use (ToU) tariffs require **global horizon awareness**:
- Discharging battery during an off-peak morning hour at 4 BDT/kWh leaves zero stored energy for a critical peak window in the afternoon at 12 BDT/kWh.
- **Simultaneous 24-Hour Linear Programming (LP)** couples all 24 hours through the battery state transition matrix, discovering the global Pareto-optimal arbitrage strategy:
  1. Absorb excess solar during mid-day.
  2. Charge from grid during off-peak windows if economical.
  3. Hold energy in reserve.
  4. Discharge aggressively during peak tariff windows to achieve maximum peak shaving.

---

## 4. End-of-Day Neutrality ($E_{23} \ge E_{\text{init}}$)

In short-horizon optimization, an algorithm without boundary conditions will "dump" 100% of stored battery energy in the final hour to artificially minimize that day's financial cost. 

In real-world campus operations, this creates a catastrophic failure mode: the battery starts at 0% on Day 2, forcing expensive grid purchases during the morning peak. GridWise enforces:
$$E_{23} \ge E_{\text{init}}$$
This constraint ensures operational sustainability across continuous multi-day cycles without artificial end-of-horizon exploitation.

---

## 5. Non-Blocking Observability

In contest environments and production API gateways:
- Automated judge harnesses grade on **latency** and **success rate**.
- Network latency to third-party databases (e.g., Supabase) or external LLM endpoints must never compromise the client response SLA.
- Telemetry persistence is decoupled into background tasks (`BackgroundTasks` + `asyncio.to_thread`).
- If Supabase is unreachable or degraded, the client still receives their verified dispatch plan in under 100ms.

---

## 6. Minimal Footprint & Zero Heavy Dependencies

- Rather than requiring proprietary external commercial solvers (like CPLEX or Gurobi) or massive native binary dependencies, GridWise relies on `scipy.optimize.linprog(method="highs")`.
- HiGHS is a world-class, open-source high-performance C++ solver built directly into standard SciPy wheels, ensuring zero-configuration portability across Linux, macOS, Windows, and Docker containers.
