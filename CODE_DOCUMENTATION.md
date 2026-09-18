# Codebase Documentation: GridWise Energy Optimization System

> Technical reference detailing the module architecture, internal data structures, algorithms, and implementation mechanics of the GridWise backend and frontend.

---

## 1. Directory & Component Architecture

```
GridMan/
├── app/
│   ├── schemas/contract.py       # Pydantic v2 domain schemas & serialization contracts
│   ├── llm/                      # Directive interpretation pipeline
│   │   ├── prompts.py            # Zero-shot system prompts with domain grammar
│   │   ├── interpreter.py        # LiteLLM client with timeout & structured JSON parsing
│   │   └── parser.py             # Deterministic regex and keyword fallback engine
│   ├── optimizer/                # Mathematical programming & validation
│   │   ├── guardrails.py         # Deterministic bounds checking & normalization
│   │   └── solver.py             # SciPy HiGHS Linear Programming (LP) formulation
│   ├── db/supabase_client.py     # Asynchronous non-blocking Supabase logger
│   ├── core/config.py            # Environment settings management
│   ├── api/routes.py             # FastAPI routing, timing middleware, exception handling
│   └── main.py                   # Application factory & CORS configuration
├── frontend/                     # React 19 + TypeScript single-page application
└── tests/                        # Pytest suite with 78 unit & integration tests
```

---

## 2. Core Modules & Implementation Details

### 2.1 Domain Schemas (`app/schemas/contract.py`)
Provides strict validation rules leveraging Pydantic v2:
- **`HourInput`**: Validates $h \in [0, 23]$, $\text{demand} \ge 0$, $\text{solar} \ge 0$, and $\text{tariff} \ge 0$.
- **`BatteryInput`**: Validates battery specs (`capacity >= 0`, `initial >= 0`, `min_reserve >= 0`, `max_charge >= 0`, `max_discharge >= 0`) and enforces that initial and minimum energy cannot exceed total capacity.
- **`DirectiveType`**: Enumeration of supported directives:
  - `solar_reduction`: Decreases solar availability by a fraction `factor` ($0.0 \dots 1.0$) across specific hours.
  - `minimum_battery_reserve`: Elevates battery lower bound to `minimum_energy_kwh` during target hours.
  - `no_charge_window`: Forbids battery charging ($C_h = 0$).
  - `no_discharge_window`: Forbids battery discharging ($D_h = 0$).
  - `max_grid_window`: Imposes an upper cap on grid import ($G_h \le G_{\max, h}$).
  - `no_op`: Irrelevant conversational noise or unparseable notes (`applies = False`).
- **`OptimizeEnergyResponse`**: Contains the full 24-hour dispatch plan, cost summaries, peak grid consumption, and sanitized directive interpretation audit trails.

### 2.2 LLM Directive Interpreter (`app/llm/interpreter.py` & `app/llm/prompts.py`)
- **System Prompt Design**: Strictly defines whole-hour, start-inclusive, end-exclusive window conventions (e.g., "1 PM to 3 PM" $\to [13, 14]$), solar reduction semantics ("drop to 20%" $\to \text{factor}=0.2$), and relative battery percentages computed against `battery.capacity_kwh`.
- **LiteLLM Provider Abstraction**: Dynamically selects available API credentials (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `GROQ_API_KEY`, `GOOGLE_API_KEY`, or `ANTHROPIC_API_KEY`).
- **Timeout & Safe Degradation**: Enforces a strict 4.0-second async timeout (`asyncio.wait_for`). If the external LLM provider stalls, errors, or is unreachable, the system automatically falls back to `app/llm/parser.py` (regex rule extractor), ensuring zero judge request drops.

### 2.3 Mathematical Guardrails (`app/optimizer/guardrails.py`)
Acts as a security and integrity firewall between the LLM output and the LP solver:
- **Index Alignment**: Enforces contiguous sorting of `note_index` matching the input list.
- **Hour Sanitization**: Clamps, filters, and deduplicates hours to valid ints $\in [0, 23]$.
- **Factor Clamping**: Clamps solar factors strictly to $[0.0, 1.0]$.
- **Capacity Bounds**: Clamps minimum battery reserves between $0.0$ and `capacity_kwh`.
- **Deterministic Distractor Neutralization**: For unrecoverable directives or `no_op`, forces `applies = False` and `structured_adjustment = None`.

### 2.4 Linear Programming Solver (`app/optimizer/solver.py`)
Formulates and solves the microgrid dispatch problem using `scipy.optimize.linprog` with the **HiGHS** simplex/interior-point backend:
- **Decision Variables (120 variables)**:
  - $0 \le G_h \le \infty$ (or max grid cap $G_{\max, h}$)
  - $0 \le S_h \le S_{\max, h}$
  - $0 \le C_h \le C_{\max, h}$
  - $0 \le D_h \le D_{\max, h}$
  - $E_{\min, h} \le E_h \le E_{\text{cap}}$
- **Equality Constraints Matrix ($A_{eq} \cdot \mathbf{x} = \mathbf{b}_{eq}$)**:
  - **Energy Balance (24 equations)**: $G_h + S_h - C_h + D_h = \text{demand}_h$
  - **Storage Dynamics (24 equations)**:
    - Hour 0: $E_0 - C_0 + D_0 = E_{\text{init}}$
    - Hours $1 \dots 23$: $E_h - E_{h-1} - C_h + D_h = 0$
- **Inequality Constraints Matrix ($A_{ub} \cdot \mathbf{x} \le \mathbf{b}_{ub}$)**:
  - **End-of-day Neutrality**: $-E_{23} \le -E_{\text{init}} \implies E_{23} \ge E_{\text{init}}$
- **Solution Verification**: Replays the solved schedule through numerical assertions, ensuring $|G + S + D - \text{demand} - C| < 10^{-3}$ and energy continuity.

### 2.5 Asynchronous Telemetry Client (`app/db/supabase_client.py`)
- Initializes a thread-safe Supabase client using `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`.
- Runs via FastAPI `BackgroundTasks` executed through `asyncio.to_thread` to prevent thread-pool blocking.
- Implements comprehensive error shielding: database timeouts, missing credentials, or table errors are logged to `stderr` without raising exceptions or impacting the client HTTP response.

### 2.6 Application Gateway (`app/main.py` & `app/api/routes.py`)
- **`GET /health`**: Returns `{"status": "ok"}` in $<10\text{ms}$ for health probes.
- **`POST /optimize-energy`**: Orchestrates latency tracking, LLM parsing, guardrail sanitization, HiGHS optimization, and background logging.
- **Error Handlers**:
  - `HTTP 400`: Returns structured error details for malformed payloads or invalid schemas.
  - `HTTP 500`: Catches unhandled exceptions and masks database URLs, API keys, or raw stack traces.

---

## 3. Frontend Architecture (`frontend/`)

- **Tech Stack**: React 19, TypeScript, Vite, Tailwind CSS v4, Lucide Icons, and Recharts.
- **Key Components**:
  - `ScheduleChart.tsx`: Stacked bar chart showing solar usage, battery discharge, and grid imports against the campus demand curve.
  - `BatterySocChart.tsx`: Area chart visualizing battery energy levels ($E_h$) over the 24-hour horizon relative to reserve thresholds.
  - `DirectiveInspector.tsx`: Interactive audit panel displaying raw operator notes, extracted JSON adjustments, and rule justifications.
  - `DispatchTable.tsx`: Tabular view of hourly dispatch metrics with CSV export functionality.
  - `lib/presets.ts`: Preloaded sample scenarios from the BUP competition case pack for one-click testing.

---

## 4. Test Suite Organization (`tests/`)

- **`test_contract.py`**: Validates boundary rules (negative demand, invalid hour index, battery capacity overflow).
- **`test_interpreter.py`**: Mocks LiteLLM calls, tests prompt formatting, verifies relative capacity calculations, and tests fallback regex parsing.
- **`test_guardrails.py`**: Tests duplicate hour removal, ascending order sorting, clamping bounds, and malformed directive recovery.
- **`test_solver.py`**: Validates mathematical optimality, zero grid usage during solar abundance, tariff peak-shaving, and end-of-day battery neutrality.
- **`test_api.py`**: Verifies HTTP status codes, latency headers, and error masking.
- **`test_public_cases.py`**: End-to-end integration test against all 10 sample cases in `BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json`.
