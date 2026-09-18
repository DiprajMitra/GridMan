"""Unit tests for app/db/supabase_client.py."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

import app.db.supabase_client as db_module
from app.db.supabase_client import (
    OPTIMIZATION_LOGS_DDL,
    get_supabase_client,
    log_optimization_result,
    log_optimization_run,
)
from app.schemas.contract import (
    BatteryAction,
    BatteryInput,
    DirectiveInterpretation,
    DirectiveType,
    HourInput,
    HourlyPlanEntry,
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
    SolarAdjustment,
)


@pytest.fixture(autouse=True)
def reset_client_singleton():
    """Ensure singleton is reset across tests."""
    db_module._supabase_client = None
    yield
    db_module._supabase_client = None


def test_ddl_columns_present():
    """Verify DDL contains table and all required columns."""
    ddl_lower = OPTIMIZATION_LOGS_DDL.lower()
    assert "create table if not exists optimization_logs" in ddl_lower
    assert "id uuid" in ddl_lower
    assert "scenario_id text" in ddl_lower
    assert "input_payload jsonb" in ddl_lower
    assert "directive_interpretation jsonb" in ddl_lower
    assert "hourly_plan jsonb" in ddl_lower
    assert "total_cost_bdt numeric" in ddl_lower
    assert "peak_grid_kwh numeric" in ddl_lower
    assert "execution_time_ms numeric" in ddl_lower
    assert "created_at timestamptz" in ddl_lower


def test_get_supabase_client_none_without_keys(monkeypatch):
    """Client should be None when keys are not configured."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)

    client = get_supabase_client()
    assert client is None


def test_get_supabase_client_with_keys(monkeypatch):
    """Client should initialize when keys are configured."""
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-key-test")

    mock_client = MagicMock()
    with patch("app.db.supabase_client.create_client", return_value=mock_client) as mock_create:
        client = get_supabase_client()
        assert client == mock_client
        mock_create.assert_called_once_with(
            "https://example.supabase.co", "service-key-test"
        )


def test_log_optimization_run_unconfigured():
    """Should return None without error if Supabase is unconfigured."""
    res = asyncio.run(
        log_optimization_run(
            scenario_id="TEST-01",
            input_payload={"test": 1},
            directive_interpretation=[],
            hourly_plan=[],
            total_cost_bdt=100.0,
            peak_grid_kwh=50.0,
            execution_time_ms=250.0,
        )
    )
    assert res is None


def test_log_optimization_run_success():
    """Should insert record and return result when client is available."""
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_insert = MagicMock()
    mock_execute = MagicMock()

    mock_execute.data = [{"id": "uuid-1234", "scenario_id": "TEST-01"}]
    mock_insert.execute.return_value = mock_execute
    mock_table.insert.return_value = mock_insert
    mock_client.table.return_value = mock_table

    with patch("app.db.supabase_client.get_supabase_client", return_value=mock_client):
        res = asyncio.run(
            log_optimization_run(
                scenario_id="TEST-01",
                input_payload={"battery": {"capacity_kwh": 200}},
                directive_interpretation=[{"note_index": 0, "applies": False}],
                hourly_plan=[{"hour": 0, "grid_kwh": 30.0}],
                total_cost_bdt=150.5,
                peak_grid_kwh=45.0,
                execution_time_ms=125.0,
            )
        )
        assert res == [{"id": "uuid-1234", "scenario_id": "TEST-01"}]
        mock_client.table.assert_called_once_with("optimization_logs")


def test_log_optimization_run_catches_exceptions():
    """Should catch database exceptions and return None without raising."""
    mock_client = MagicMock()
    mock_client.table.side_effect = RuntimeError("Database unreachable")

    with patch("app.db.supabase_client.get_supabase_client", return_value=mock_client):
        res = asyncio.run(
            log_optimization_run(
                scenario_id="TEST-01",
                input_payload={},
                directive_interpretation=[],
                hourly_plan=[],
                total_cost_bdt=0.0,
                peak_grid_kwh=0.0,
                execution_time_ms=10.0,
            )
        )
        assert res is None


def test_log_optimization_result_typed():
    """Should accept typed Pydantic models in log_optimization_result."""
    hours = [
        HourInput(hour=h, demand_kwh=50, solar_kwh=0, tariff_bdt_per_kwh=5)
        for h in range(24)
    ]
    battery = BatteryInput(
        capacity_kwh=200,
        initial_energy_kwh=100,
        minimum_energy_kwh=40,
        max_charge_kwh_per_hour=50,
        max_discharge_kwh_per_hour=50,
    )
    req = OptimizeEnergyRequest(
        scenario_id="GRID-TYPED",
        operator_notes=["Note"],
        hours=hours,
        battery=battery,
    )
    resp = OptimizeEnergyResponse(
        scenario_id="GRID-TYPED",
        directive_interpretation=[
            DirectiveInterpretation(
                note_index=0,
                applies=True,
                directive_type=DirectiveType.SOLAR_REDUCTION,
                structured_adjustment=SolarAdjustment(hours=[12], factor=0.5),
                explanation="Reduced solar",
            )
        ],
        hourly_plan=[
            HourlyPlanEntry(
                hour=h,
                grid_kwh=50.0,
                solar_used_kwh=0.0,
                battery_action=BatteryAction.IDLE,
                battery_kwh=0.0,
                battery_energy_after_kwh=100.0,
            )
            for h in range(24)
        ],
        total_grid_kwh=1200.0,
        total_cost_bdt=6000.0,
        peak_grid_kwh=50.0,
        plan_summary="Plan summary",
    )

    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_insert = MagicMock()
    mock_execute = MagicMock()

    mock_execute.data = [{"id": "uuid-999"}]
    mock_insert.execute.return_value = mock_execute
    mock_table.insert.return_value = mock_insert
    mock_client.table.return_value = mock_table

    with patch("app.db.supabase_client.get_supabase_client", return_value=mock_client):
        res = asyncio.run(log_optimization_result(req, resp, execution_time_ms=85.5))
        assert res == [{"id": "uuid-999"}]
