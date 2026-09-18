# GridWise (GridMan) — Smart Campus Energy Optimization Engine

> **BUP CSE Fest 2026 — Preliminary Hackathon Round**  
> High-performance microgrid dispatch optimization engine combining LLM natural language directive extraction with deterministic SciPy HiGHS Linear Programming.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19.x-blue.svg)](https://react.dev/)
[![Tailwind CSS v4](https://img.shields.io/badge/Tailwind-v4.x-38B2AC.svg)](https://tailwindcss.com/)
[![Tests](https://img.shields.io/badge/Tests-78%20Passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 1. System Architecture

GridWise operates on a strict **separation of concerns**:
- **Fuzzy Layer**: Generative AI (LiteLLM with Gemini / OpenAI / Groq) is strictly confined to natural language parsing and JSON extraction.
- **Verification Layer**: Deterministic guardrails validate, clamp, and sanitize operator directives.
- **Optimization Layer**: Exact mathematical programming (SciPy HiGHS Simplex / Interior-Point LP) computes the mathematically optimal 24-hour dispatch schedule.
- **Observability Layer**: Non-blocking asynchronous telemetry logs runs to Supabase without penalizing HTTP response latency.

```
                   ┌─────────────────────────────────────────┐
                   │    Client (Web Dashboard / Judge CLI)   │
                   └────────────────────┬────────────────────┘
                                        │ HTTP POST /optimize-energy
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │        FastAPI Application Gateway      │
                   │  - Latency Timer & CORS Middleware      │
                   │  - Pydantic v2 Schema Contract Validation│
                   └────────────────────┬────────────────────┘
                                        │
                 ┌──────────────────────┴──────────────────────┐
                 ▼                                             ▼
  ┌──────────────────────────────┐              ┌──────────────────────────────┐
  │   LLM Directive Interpreter  │              │    Fallback Rule Extractor   │
  │  (LiteLLM / Gemini / OpenAI) │ ──(Timeout)──▶  (Deterministic Regex/Heur)  │
  └──────────────┬───────────────┘              └──────────────┬───────────────┘
                 │                                             │
                 └──────────────────────┬──────────────────────┘
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │      Deterministic Guardrails Engine    │
                   │  - Array bound & hour clamping (0..23)  │
                   │  - Battery capacity reserve enforcement │
                   │  - No-op & distractor filtering         │
                   └────────────────────┬────────────────────┘
                                        │
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │      SciPy HiGHS LP Solver (120 vars)   │
                   │  - Energy balance: G + S + D = L + C    │
                   │  - Battery dynamics: E[h] = E[h-1]+C-D  │
                   │  - End-of-day neutrality (E_23 >= E_0)  │
                   │  - Time-of-Use cost minimization        │
                   └────────────────────┬────────────────────┘
                                        │
                 ┌──────────────────────┴──────────────────────┐
                 │                                             │
                 ▼                                             ▼
  ┌──────────────────────────────┐              ┌──────────────────────────────┐
  │   Immediate HTTP 200 JSON    │              │ Background Supabase Logger   │
  │  (Within <100ms - 1.5s SLA)  │              │ (Async non-blocking worker)  │
  └──────────────────────────────┘              └──────────────────────────────┘
```

---

## 2. Mathematical Formulation

The optimization problem is formulated as a 24-hour horizon **Linear Program (LP)** with $24 \times 5 = 120$ continuous decision variables:

$$\mathbf{x} = [G_0 \dots G_{23},\, S_0 \dots S_{23},\, C_0 \dots C_{23},\, D_0 \dots D_{23},\, E_0 \dots E_{23}]^T$$

### 2.1 Decision Variables (for $h \in \{0, \dots, 23\}$)
- $G_h \ge 0$: Energy imported from the utility grid (kWh).
- $S_h \ge 0$: Solar power consumed on-site (kWh).
- $C_h \ge 0$: Energy charged into the battery storage system (kWh).
- $D_h \ge 0$: Energy discharged from the battery (kWh).
- $E_h \ge 0$: Battery State of Charge (energy stored) at the end of hour $h$ (kWh).

### 2.2 Objective Function
Minimize the total cost of electricity purchased from the utility grid under Time-of-Use (ToU) tariffs, plus an infinitesimal degradation penalty $\epsilon = 10^{-5}$ to discourage unnecessary battery cycling:

$$\min_{\mathbf{x}} \sum_{h=0}^{23} \left( \text{tariff}_h \cdot G_h + \epsilon \cdot (C_h + D_h) \right)$$

### 2.3 System Constraints

1. **Hourly Energy Balance:**
   $$G_h + S_h + D_h = \text{demand}_h + C_h \quad \forall h \in \{0, \dots, 23\}$$

2. **Solar Resource Bounds:**
   $$0 \le S_h \le \text{solar}_h \cdot \alpha_h$$
   where $\alpha_h \in [0.0, 1.0]$ represents the solar availability factor resulting from operator directives (e.g., panel cleaning, cloud cover).

3. **Battery Storage Dynamics:**
   $$E_h = E_{h-1} + C_h - D_h \quad \text{for } h \ge 1$$
   $$E_0 = E_{\text{init}} + C_0 - D_0 \quad \text{for } h = 0$$

4. **Battery Energy Bounds:**
   $$\max(\text{min\_energy}, \text{reserve}_h) \le E_h \le \text{capacity} \quad \forall h$$

5. **Charge and Discharge Rate Limits:**
   $$0 \le C_h \le \begin{cases} 0 & \text{if } h \in \text{no\_charge\_window} \\ \text{max\_charge\_rate} & \text{otherwise} \end{cases}$$
   $$0 \le D_h \le \begin{cases} 0 & \text{if } h \in \text{no\_discharge\_window} \\ \text{max\_discharge\_rate} & \text{otherwise} \end{cases}$$

6. **Grid Import Limit (Optional Operator Constraint):**
   $$0 \le G_h \le \text{max\_grid\_kwh}_h \quad \text{if directive active}$$

7. **End-of-Day Neutrality:**
   $$E_{23} \ge E_{\text{init}}$$
   Prevents artificial depletion of battery reserves to ensure the campus remains resilient for the subsequent operating day.

---

## 3. Features

- **Pydantic v2 Contract Enforcing**: Full input/output schema validation guaranteeing 100% adherence to the BUP CSE Fest specification.
- **Resilient Multi-Provider LLM Integration**: Powered by `litellm` supporting Google Gemini, OpenAI GPT-4o, Groq Llama-3, and Claude 3.5, with automatic timeout fallback.
- **Fail-Safe Regex Parser**: Instant zero-latency regex rule fallback if external LLM APIs timeout, error, or encounter rate limits.
- **Deterministic Guardrails**: Validates and normalizes hour windows, clamps solar factors ($0.0 \dots 1.0$), validates battery capacity ranges, and rejects irrelevant conversational distractors.
- **Sub-100ms HiGHS LP Solver**: Direct C++ interior-point/simplex solver via SciPy, solving in 10-25 milliseconds.
- **Post-Solve Energy Balance Replay Audit**: Validates numerical precision ($|G + S + D - L - C| < 10^{-3}$) before returning the payload.
- **Decoupled Telemetry Logging**: Asynchronous Supabase logging via FastAPI `BackgroundTasks` — database outages never block API responses.
- **Full Interactive React UI**: Real-time dashboard with Recharts visualization for 24-hour generation/consumption dispatch, battery state-of-charge curves, directive inspectors, and preloaded sample cases.

---

## 4. Project Structure

```
GridMan/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py              # GET /health, POST /optimize-energy
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py              # Pydantic BaseSettings & env loader
│   ├── db/
│   │   ├── __init__.py
│   │   └── supabase_client.py     # Asynchronous background telemetry logger
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── interpreter.py        # LiteLLM operator directive parser
│   │   ├── parser.py             # Deterministic regex fallback parser
│   │   └── prompts.py            # Strict zero-shot system prompt
│   ├── optimizer/
│   │   ├── __init__.py
│   │   ├── guardrails.py         # Constraint validation & sanitization
│   │   └── solver.py             # 120-variable SciPy HiGHS LP solver
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── contract.py           # Pydantic v2 domain models
│   └── main.py                   # FastAPI app creation & lifecycle
├── frontend/                     # React 19 + TypeScript + Vite + TailwindCSS
│   ├── src/
│   │   ├── components/           # UI cards, dispatch charts, SOC graphs
│   │   ├── lib/                  # API client & scenario presets
│   │   └── App.tsx               # Main dashboard component
│   └── package.json
├── tests/                        # 78 comprehensive unit & integration tests
│   ├── test_api.py               # API endpoints, error handling, health
│   ├── test_contract.py          # Pydantic validation & boundary tests
│   ├── test_guardrails.py        # Clamping and normalization tests
│   ├── test_interpreter.py       # LLM prompt and regex fallback tests
│   ├── test_public_cases.py      # Official BUP sample cases
│   ├── test_solver.py            # Mathematical LP solver tests
│   └── test_supabase_client.py   # Telemetry client tests
├── Dockerfile                    # Multi-stage non-root container
├── .dockerignore
├── requirements.txt              # Core Python dependencies
├── run_local.sh                  # One-command local startup script
├── run_docker.sh                 # Docker build & run script
├── test_endpoints.sh             # Live curl verification script
└── BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json # Official contest dataset
```

---

## 5. Quick Start

### 5.1 Prerequisites
- Python 3.11 or 3.12
- Node.js 18+ and npm (for frontend)
- Docker & Docker Compose (optional, for containerized run)

### 5.2 Local Setup (Backend)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/DiprajMitra/GridMan.git
   cd GridMan
   ```

2. **Create a virtual environment & install dependencies:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   Create a `.env` file in the root directory (or export variables):
   ```bash
   # LLM API Keys (At least one recommended; defaults to regex fallback if omitted)
   GEMINI_API_KEY="your-gemini-api-key"
   # OPENAI_API_KEY="your-openai-api-key"
   # GROQ_API_KEY="your-groq-api-key"

   # Supabase Telemetry (Optional; runs cleanly without it)
   SUPABASE_URL="https://your-project.supabase.co"
   SUPABASE_SERVICE_KEY="your-service-role-key"

   # Server Config
   PORT=8000
   HOST="0.0.0.0"
   LOG_LEVEL="info"
   ```

4. **Launch the backend server:**
   ```bash
   ./run_local.sh
   # Or directly:
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   API will be live at: `http://localhost:8000`  
   Interactive Swagger docs: `http://localhost:8000/docs`

### 5.3 Local Setup (Frontend)

```bash
cd frontend
npm install
npm run dev
```
Dashboard will be live at: `http://localhost:5173`

---

## 6. Running with Docker

The project includes a production-ready, non-root `Dockerfile`:

### 6.1 Build and Run via Helper Script
```bash
chmod +x run_docker.sh
./run_docker.sh
```

### 6.2 Manual Docker Commands
```bash
# Build image
docker build -t gridman:v2 .

# Run container exposing port 8000
docker run --rm -p 8000:8000 \
  -e GEMINI_API_KEY="${GEMINI_API_KEY}" \
  -e SUPABASE_URL="${SUPABASE_URL}" \
  -e SUPABASE_SERVICE_KEY="${SUPABASE_SERVICE_KEY}" \
  gridman:v2
```

---

## 7. API Reference

### 7.1 Health Check
- **Endpoint**: `GET /health`
- **Latency**: `< 10ms`
- **Response** (`200 OK`):
  ```json
  {
    "status": "ok"
  }
  ```

### 7.2 Optimize Energy Schedule
- **Endpoint**: `POST /optimize-energy`
- **Request Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "scenario_id": "GRID-101",
    "operator_notes": [
      "Solar output will drop to about 20% from 1 PM to 3 PM due to panel cleaning.",
      "Do not charge the battery between 2 PM and 4 PM."
    ],
    "hours": [
      {
        "hour": 0,
        "demand_kwh": 45.0,
        "solar_kwh": 0.0,
        "tariff_bdt_per_kwh": 6.5
      }
      // ... 24 items (hours 0 to 23)
    ],
    "battery": {
      "capacity_kwh": 200.0,
      "initial_energy_kwh": 80.0,
      "minimum_energy_kwh": 40.0,
      "max_charge_kwh_per_hour": 50.0,
      "max_discharge_kwh_per_hour": 50.0
    }
  }
  ```

- **Response (`200 OK`)**:
  ```json
  {
    "scenario_id": "GRID-101",
    "directive_interpretation": [
      {
        "note_index": 0,
        "raw_note": "Solar output will drop to about 20% from 1 PM to 3 PM due to panel cleaning.",
        "applies": true,
        "directive_type": "solar_reduction",
        "structured_adjustment": {
          "hours": [13, 14],
          "factor": 0.2
        },
        "reasoning": "Panel cleaning reduces solar to 20% between 13:00 and 15:00."
      },
      {
        "note_index": 1,
        "raw_note": "Do not charge the battery between 2 PM and 4 PM.",
        "applies": true,
        "directive_type": "no_charge_window",
        "structured_adjustment": {
          "hours": [14, 15]
        },
        "reasoning": "Battery charging forbidden between 14:00 and 16:00."
      }
    ],
    "hourly_plan": [
      {
        "hour": 0,
        "grid_import_kwh": 45.0,
        "solar_used_kwh": 0.0,
        "battery_charge_kwh": 0.0,
        "battery_discharge_kwh": 0.0,
        "battery_energy_kwh": 80.0,
        "cost_bdt": 292.5
      }
      // ... 24 entries
    ],
    "total_grid_kwh": 1240.5,
    "total_cost_bdt": 8420.25,
    "peak_grid_kwh": 95.0,
    "plan_summary": "Optimal 24-hour schedule generated using HiGHS LP solver. Total cost: 8420.25 BDT across 1240.50 kWh grid imports."
  }
  ```

---

## 8. Verification & Testing

The repository contains an exhaustive automated test suite with **78 tests** covering unit, integration, edge, and competition benchmark scenarios.

```bash
# Run entire test suite
pytest -v

# Run endpoint verification curl script
./test_endpoints.sh
```

### Test Coverage Highlights:
- `test_contract.py`: 24 validation tests for boundary values, missing keys, and schema integrity.
- `test_interpreter.py`: 17 tests covering standard directives, complex multi-hour windows, relative battery percentages, and distractor noise rejection.
- `test_guardrails.py`: 10 tests verifying hour sorting, factor clamping ($0.0 \dots 1.0$), reserve boundaries, and safe recovery.
- `test_solver.py`: 6 rigorous mathematical tests validating energy balance precision, ToU peak-shaving, storage bounds, and end-of-day reserve preservation.
- `test_api.py`: 9 integration tests testing endpoints, 400 bad JSON handling, 500 secret-masking safety, and timing.
- `test_public_cases.py`: Direct end-to-end verification against all 10 official BUP CSE Fest competition test cases (`BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json`).

---

## 9. Telemetry & Database Schema (Supabase)

To enable persistent audit trails, GridWise logs every optimization run asynchronously. Run the following DDL in your Supabase SQL Editor:

```sql
CREATE TABLE IF NOT EXISTS optimization_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id TEXT NOT NULL,
    operator_notes JSONB NOT NULL,
    directive_interpretation JSONB NOT NULL,
    hourly_plan JSONB NOT NULL,
    total_grid_kwh NUMERIC(12, 4) NOT NULL,
    total_cost_bdt NUMERIC(12, 4) NOT NULL,
    peak_grid_kwh NUMERIC(10, 4) NOT NULL,
    plan_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_optimization_logs_scenario_id ON optimization_logs (scenario_id);
CREATE INDEX IF NOT EXISTS idx_optimization_logs_created_at ON optimization_logs (created_at DESC);
```

---

## 10. Contributors & License

- **Developed for**: BUP CSE Fest 2026 — Preliminary Hackathon Round
- **Team / Author**: Dipraj Mitra
- **Repository**: [https://github.com/DiprajMitra/GridMan](https://github.com/DiprajMitra/GridMan)
- **License**: [MIT License](LICENSE)
