"""Public scenario integration test cases conforming to BUP CSE Fest 2026."""

from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)


def make_hours(demand_base: float, solar_peak: float, tariff_normal: float, tariff_peak: float = 12.0) -> list[dict]:
    """Helper to generate standard 24-hour profiles."""
    return [
        {
            "hour": h,
            "demand_kwh": demand_base + (30.0 if 9 <= h <= 17 else 0.0),
            "solar_kwh": max(0.0, solar_peak - abs(h - 12) * (solar_peak / 6.0)),
            "tariff_bdt_per_kwh": tariff_peak if 12 <= h <= 16 else tariff_normal,
        }
        for h in range(24)
    ]


def make_battery(cap: float = 200.0, init: float = 100.0, min_res: float = 40.0, max_ch: float = 50.0, max_dis: float = 50.0) -> dict:
    """Helper to generate standard battery configuration."""
    return {
        "capacity_kwh": cap,
        "initial_energy_kwh": init,
        "minimum_energy_kwh": min_res,
        "max_charge_kwh_per_hour": max_ch,
        "max_discharge_kwh_per_hour": max_dis,
    }


class TestPublicScenarios:
    """Verify end-to-end optimization behavior on representative competition cases."""

    def test_scenario_grid_101_standard_day(self):
        payload = {
            "scenario_id": "GRID-101",
            "operator_notes": [
                "Solar output will drop to about 20% from 1 PM to 3 PM due to panel cleaning.",
                "Do not charge the battery between 2 PM and 4 PM.",
            ],
            "hours": make_hours(demand_base=60.0, solar_peak=140.0, tariff_normal=5.0),
            "battery": make_battery(cap=200.0, init=100.0, min_res=40.0),
        }
        resp = client.post("/optimize-energy", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario_id"] == "GRID-101"
        assert len(data["hourly_plan"]) == 24
        assert data["total_grid_kwh"] > 0
        assert data["total_cost_bdt"] > 0

    def test_scenario_grid_103_event_day_no_discharge(self):
        payload = {
            "scenario_id": "GRID-103",
            "operator_notes": [
                "Large auditorium event from 10 AM to 2 PM.",
                "Do not discharge battery during event hours to preserve emergency reserve.",
            ],
            "hours": make_hours(demand_base=70.0, solar_peak=130.0, tariff_normal=5.0),
            "battery": make_battery(cap=200.0, init=150.0, min_res=60.0, max_ch=40.0, max_dis=40.0),
        }
        resp = client.post("/optimize-energy", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["hourly_plan"]) == 24

    def test_scenario_grid_105_exam_week_reserve(self):
        payload = {
            "scenario_id": "GRID-105",
            "operator_notes": [
                "Library and study halls open until midnight.",
                "Maintain at least 80 kWh battery reserve after 6 PM for emergency lighting.",
            ],
            "hours": make_hours(demand_base=80.0, solar_peak=140.0, tariff_normal=6.0),
            "battery": make_battery(cap=250.0, init=130.0, min_res=40.0),
        }
        resp = client.post("/optimize-energy", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["hourly_plan"]) == 24

    def test_scenario_grid_110_distractor_notes(self):
        payload = {
            "scenario_id": "GRID-110",
            "operator_notes": [
                "The campus gardener mentioned flowers are blooming nicely this week.",
                "Parking lot B will be repainted next Tuesday.",
                "Cafeteria menu changed to include more vegetarian options.",
            ],
            "hours": make_hours(demand_base=60.0, solar_peak=140.0, tariff_normal=5.0),
            "battery": make_battery(cap=200.0, init=100.0, min_res=40.0),
        }
        resp = client.post("/optimize-energy", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["directive_interpretation"]) == 3
        assert all(d["applies"] is False for d in data["directive_interpretation"])
        assert all(d["directive_type"] == "no_op" for d in data["directive_interpretation"])
        assert all(d["structured_adjustment"] is None for d in data["directive_interpretation"])

    def test_all_10_official_sample_cases_from_pack(self):
        import json, os
        pack_path = "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
        if not os.path.exists(pack_path):
            pytest.skip("Public sample case pack not found")

        with open(pack_path) as f:
            pack = json.load(f)

        for case in pack["cases"]:
            resp = client.post("/optimize-energy", json=case["input"])
            assert resp.status_code == 200, f"Case {case['id']} failed with {resp.status_code}: {resp.text}"
            data = resp.json()
            assert data["scenario_id"] == case["input"]["scenario_id"]
            assert len(data["hourly_plan"]) == 24
            assert data["total_grid_kwh"] >= 0
            assert data["total_cost_bdt"] >= 0
            assert data["peak_grid_kwh"] >= 0
