"""Integration and end-to-end API tests for app/main.py."""

import time
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.schemas.contract import DirectiveInterpretation, DirectiveType, SolarAdjustment

client = TestClient(app)


def get_valid_payload() -> dict:
    """Helper to produce a valid 24-hour request dictionary."""
    return {
        "scenario_id": "GRID-API-01",
        "operator_notes": [
            "Solar will drop to 20% from 1 PM to 3 PM.",
            "Do not charge battery between 2 PM and 4 PM.",
        ],
        "hours": [
            {
                "hour": h,
                "demand_kwh": 60.0 + (20.0 if 10 <= h <= 16 else 0.0),
                "solar_kwh": max(0.0, 100.0 - abs(h - 12) * 15.0),
                "tariff_bdt_per_kwh": 10.0 if 12 <= h <= 15 else 5.0,
            }
            for h in range(24)
        ],
        "battery": {
            "capacity_kwh": 200.0,
            "initial_energy_kwh": 100.0,
            "minimum_energy_kwh": 40.0,
            "max_charge_kwh_per_hour": 50.0,
            "max_discharge_kwh_per_hour": 50.0,
        },
    }


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_check_status_and_latency(self):
        start = time.perf_counter()
        resp = client.get("/health")
        latency_ms = (time.perf_counter() - start) * 1000

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        # Verify executed well within latency requirement
        assert latency_ms < 50.0

    def test_health_check_prefixed(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestOptimizeEnergyEndpoint:
    """Tests for POST /optimize-energy pipeline."""

    def test_successful_optimization_pipeline(self):
        payload = get_valid_payload()

        mock_directives = [
            DirectiveInterpretation(
                note_index=0,
                applies=True,
                directive_type=DirectiveType.SOLAR_REDUCTION,
                structured_adjustment=SolarAdjustment(hours=[13, 14], factor=0.2),
                explanation="Mocked solar reduction",
            ),
            DirectiveInterpretation(
                note_index=1,
                applies=False,
                directive_type=DirectiveType.NO_OP,
                structured_adjustment=None,
                explanation="No charge mocked",
            ),
        ]

        with patch("app.api.routes.interpret_operator_notes", new=AsyncMock(return_value=mock_directives)):
            with patch("app.api.routes.log_optimization_result", new=AsyncMock()) as mock_log:
                resp = client.post("/optimize-energy", json=payload)
                assert resp.status_code == 200
                data = resp.json()

                assert data["scenario_id"] == "GRID-API-01"
                assert len(data["hourly_plan"]) == 24
                assert len(data["directive_interpretation"]) == 2
                assert data["total_grid_kwh"] > 0
                assert data["total_cost_bdt"] > 0
                assert data["peak_grid_kwh"] > 0
                assert "plan_summary" in data

    def test_validation_error_empty_body(self):
        resp = client.post("/optimize-energy", json={})
        assert resp.status_code == 400
        data = resp.json()
        assert "message" in data
        assert "detail" in data

    def test_validation_error_hours_not_24(self):
        payload = get_valid_payload()
        payload["hours"] = payload["hours"][:23]  # Only 23 hours
        resp = client.post("/optimize-energy", json=payload)
        assert resp.status_code == 400

    def test_validation_error_negative_values(self):
        payload = get_valid_payload()
        payload["battery"]["capacity_kwh"] = -50.0  # Invalid negative capacity
        resp = client.post("/optimize-energy", json=payload)
        assert resp.status_code == 400

    def test_validation_error_empty_operator_notes(self):
        payload = get_valid_payload()
        payload["operator_notes"] = []
        resp = client.post("/optimize-energy", json=payload)
        assert resp.status_code == 400

    def test_validation_error_whitespace_operator_note(self):
        payload = get_valid_payload()
        payload["operator_notes"] = ["   "]
        resp = client.post("/optimize-energy", json=payload)
        assert resp.status_code == 400

    def test_internal_error_sanitized_response(self):
        payload = get_valid_payload()

        # Simulate unexpected internal failure in solver
        with patch("app.api.routes.solve_schedule", side_effect=Exception("SecretDBConnectionFailed: user=admin pass=1234")):
            resp = client.post("/optimize-energy", json=payload)
            assert resp.status_code == 500
            data = resp.json()
            # Assert no sensitive info leaked
            assert "pass=1234" not in str(data)
            assert "SecretDBConnectionFailed" not in str(data)
            assert "internal server error" in data["detail"].lower()
