"""End-to-End QA Automation Pipeline Tests for GridWise Energy Optimization.

Validates the full system against all 10 official public sample cases in
BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json conforming strictly to
competition specifications.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)

SAMPLE_PACK_PATH = Path("BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json")


def load_sample_cases() -> List[Dict[str, Any]]:
    """Ingest all 10 sample cases from public benchmark dataset."""
    if not SAMPLE_PACK_PATH.exists():
        pytest.skip(f"Benchmark dataset {SAMPLE_PACK_PATH} not found.")

    with open(SAMPLE_PACK_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("cases", [])


CASES = load_sample_cases()
CASE_IDS = [c["id"] for c in CASES]


class TestPipelineHealth:
    """Validate system availability and health probe responses."""

    def test_health_check_status_ok(self):
        """Verify GET /health returns HTTP 200 with status 'ok' within SLA."""
        response = client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload.get("status") == "ok"


class TestPipelineSampleCases:
    """Validate end-to-end optimization pipeline on all 10 official competition sample cases."""

    @pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
    def test_case_e2e_pipeline(self, case: Dict[str, Any]):
        """Execute end-to-end validation for a public competition benchmark case.

        Verifies:
        1. HTTP 200 response from POST /optimize-energy.
        2. Accurate extraction of directive types, hours, and numerical adjustments.
        3. Hourly energy balance conservation (grid + solar_used + discharge == demand + charge).
        4. Battery end-of-day neutrality (energy_after[23] == initial_energy).
        5. Total operational cost matching reference within 0.01 BDT official tolerance.
        6. Total grid import and peak grid import integrity.
        """
        case_id = case["id"]
        input_payload = case["input"]
        expected_output = case["expected_output"]

        # Step 1: Dispatch optimization request
        response = client.post("/optimize-energy", json=input_payload)
        assert response.status_code == 200, f"Case {case_id} failed with {response.status_code}: {response.text}"
        actual_output = response.json()

        # Step 2: Validate scenario identifier
        assert actual_output.get("scenario_id") == input_payload["scenario_id"]

        # Step 3: Validate directive interpretation
        expected_directives = expected_output["directive_interpretation"]
        actual_directives = actual_output.get("directive_interpretation", [])
        assert len(actual_directives) == len(expected_directives), (
            f"Case {case_id}: Expected {len(expected_directives)} directives, got {len(actual_directives)}"
        )

        for idx, (exp_d, act_d) in enumerate(zip(expected_directives, actual_directives)):
            assert act_d["note_index"] == exp_d["note_index"], (
                f"Case {case_id} Note {idx}: note_index mismatch"
            )
            assert act_d["applies"] == exp_d["applies"], (
                f"Case {case_id} Note {idx}: applies mismatch ({act_d['applies']} vs {exp_d['applies']})"
            )
            assert act_d["directive_type"] == exp_d["directive_type"], (
                f"Case {case_id} Note {idx}: directive_type mismatch ({act_d['directive_type']} vs {exp_d['directive_type']})"
            )

            exp_adj = exp_d.get("structured_adjustment")
            act_adj = act_d.get("structured_adjustment")

            if exp_adj is None:
                assert act_adj is None, (
                    f"Case {case_id} Note {idx}: expected None structured_adjustment, got {act_adj}"
                )
            else:
                assert act_adj is not None, (
                    f"Case {case_id} Note {idx}: expected structured_adjustment, got None"
                )
                assert act_adj.get("hours") == exp_adj.get("hours"), (
                    f"Case {case_id} Note {idx}: hours mismatch ({act_adj.get('hours')} vs {exp_adj.get('hours')})"
                )

                # Validate specific numerical adjustments
                for key in ["factor", "minimum_energy_kwh", "max_grid_kwh"]:
                    if key in exp_adj:
                        assert key in act_adj, f"Case {case_id} Note {idx}: missing key '{key}' in adjustment"
                        assert abs(act_adj[key] - exp_adj[key]) < 0.01, (
                            f"Case {case_id} Note {idx}: '{key}' mismatch (got {act_adj[key]}, expected {exp_adj[key]})"
                        )

        # Step 4: Validate hourly plan length
        hourly_plan = actual_output.get("hourly_plan", [])
        assert len(hourly_plan) == 24, f"Case {case_id}: hourly_plan must contain exactly 24 entries"

        input_hours = input_payload["hours"]

        # Step 5: Validate hourly energy balance conservation
        for h in range(24):
            plan_entry = hourly_plan[h]
            hour_input = input_hours[h]

            assert plan_entry["hour"] == h, f"Case {case_id}: hour index mismatch at {h}"

            grid_kwh = plan_entry["grid_kwh"]
            solar_used_kwh = plan_entry["solar_used_kwh"]
            battery_action = plan_entry.get("battery_action", "idle")
            battery_kwh = plan_entry.get("battery_kwh", 0.0)

            battery_charge_kwh = battery_kwh if battery_action == "charge" else 0.0
            battery_discharge_kwh = battery_kwh if battery_action == "discharge" else 0.0
            demand_kwh = hour_input["demand_kwh"]

            # Energy balance: grid + solar_used + discharge == demand + charge
            generation_and_imports = grid_kwh + solar_used_kwh + battery_discharge_kwh
            load_and_storage = demand_kwh + battery_charge_kwh
            balance_diff = abs(generation_and_imports - load_and_storage)

            assert balance_diff < 0.01, (
                f"Case {case_id} Hour {h}: Energy balance violation. "
                f"Supply={generation_and_imports:.4f}, Demand={load_and_storage:.4f}, Diff={balance_diff:.4f}"
            )

        # Step 6: Validate end-of-day battery energy neutrality
        initial_battery_energy = input_payload["battery"]["initial_energy_kwh"]
        final_battery_energy = hourly_plan[23]["battery_energy_after_kwh"]
        eod_diff = abs(final_battery_energy - initial_battery_energy)

        assert eod_diff < 0.01, (
            f"Case {case_id}: End-of-day battery neutrality violation. "
            f"Initial={initial_battery_energy:.2f} kWh, Final={final_battery_energy:.2f} kWh, Diff={eod_diff:.4f}"
        )

        # Step 7: Validate total financial cost within 0.01 BDT tolerance
        actual_cost_bdt = actual_output.get("total_cost_bdt", 0.0)
        expected_cost_bdt = expected_output["total_cost_bdt"]
        cost_diff = abs(actual_cost_bdt - expected_cost_bdt)

        assert cost_diff < 0.01, (
            f"Case {case_id}: Total cost mismatch. "
            f"Actual={actual_cost_bdt:.2f} BDT, Expected={expected_cost_bdt:.2f} BDT, Diff={cost_diff:.4f} BDT"
        )

        # Step 8: Validate total grid energy import within 0.01 kWh tolerance
        actual_grid_kwh = actual_output.get("total_grid_kwh", 0.0)
        expected_grid_kwh = expected_output["total_grid_kwh"]
        grid_diff = abs(actual_grid_kwh - expected_grid_kwh)

        assert grid_diff < 0.01, (
            f"Case {case_id}: Total grid kWh mismatch. "
            f"Actual={actual_grid_kwh:.2f} kWh, Expected={expected_grid_kwh:.2f} kWh, Diff={grid_diff:.4f} kWh"
        )

        # Step 9: Validate peak grid import within 0.01 kWh tolerance
        actual_peak_kwh = actual_output.get("peak_grid_kwh", 0.0)
        expected_peak_kwh = expected_output["peak_grid_kwh"]
        peak_diff = abs(actual_peak_kwh - expected_peak_kwh)

        assert peak_diff < 0.01, (
            f"Case {case_id}: Peak grid kWh mismatch. "
            f"Actual={actual_peak_kwh:.2f} kWh, Expected={expected_peak_kwh:.2f} kWh, Diff={peak_diff:.4f} kWh"
        )
