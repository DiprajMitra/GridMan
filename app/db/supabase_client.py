"""Supabase client and non-blocking background logger for optimization runs.

Persists scenario inputs, LLM directive interpretations, optimized schedules,
and performance metrics to Supabase PostgreSQL without blocking API responses.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Union

from supabase import Client, create_client

from app.core.config import settings
from app.schemas.contract import (
    DirectiveInterpretation,
    HourlyPlanEntry,
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
)

logger = logging.getLogger("gridwise.db.supabase")

# ============================================================================
# SQL DDL Specification for Supabase
# ============================================================================

OPTIMIZATION_LOGS_DDL = """
-- Optimization run persistence schema for GridWise energy optimizer
CREATE TABLE IF NOT EXISTS optimization_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id TEXT NOT NULL,
    input_payload JSONB NOT NULL,
    directive_interpretation JSONB NOT NULL,
    hourly_plan JSONB NOT NULL,
    total_cost_bdt NUMERIC(12, 4) NOT NULL,
    peak_grid_kwh NUMERIC(10, 4) NOT NULL,
    execution_time_ms NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Performance indexes for lookup and reporting
CREATE INDEX IF NOT EXISTS idx_optimization_logs_scenario_id ON optimization_logs (scenario_id);
CREATE INDEX IF NOT EXISTS idx_optimization_logs_created_at ON optimization_logs (created_at DESC);
"""

# Cached singleton client instance
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """Retrieve or initialize the Supabase client using environment or configuration settings.

    Returns None gracefully if SUPABASE_URL or SUPABASE_SERVICE_KEY is not set.
    """
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    url = (
        os.getenv("SUPABASE_URL")
        or getattr(settings, "SUPABASE_URL", None)
    )
    key = (
        os.getenv("SUPABASE_SERVICE_KEY")
        or getattr(settings, "SUPABASE_SERVICE_KEY", None)
        or os.getenv("SUPABASE_KEY")
        or getattr(settings, "SUPABASE_KEY", None)
    )

    if not url or not key:
        logger.debug("Supabase credentials not configured; persistence disabled.")
        return None

    try:
        _supabase_client = create_client(url, key)
        return _supabase_client
    except Exception as exc:
        logger.warning("Failed to initialize Supabase client: %s", exc)
        return None


def _to_json_compatible(obj: Any) -> Any:
    """Recursively convert Pydantic models, lists, and dicts to JSON-serializable primitives."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [_to_json_compatible(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _to_json_compatible(v) for k, v in obj.items()}
    return obj


async def log_optimization_run(
    scenario_id: str,
    input_payload: Union[OptimizeEnergyRequest, Dict[str, Any]],
    directive_interpretation: Union[List[DirectiveInterpretation], List[Dict[str, Any]]],
    hourly_plan: Union[List[HourlyPlanEntry], List[Dict[str, Any]]],
    total_cost_bdt: float,
    peak_grid_kwh: float,
    execution_time_ms: float,
) -> Optional[Dict[str, Any]]:
    """Persist an optimization run record into Supabase asynchronously.

    Designed for invocation within FastAPI BackgroundTasks. All database
    and network exceptions are safely trapped so logging failures never affect
    the API response.

    Parameters
    ----------
    scenario_id : str
        The unique scenario identifier.
    input_payload : OptimizeEnergyRequest | dict
        The full input payload sent by the user or test harness.
    directive_interpretation : list[DirectiveInterpretation] | list[dict]
        Extracted directives and guardrail outputs.
    hourly_plan : list[HourlyPlanEntry] | list[dict]
        The 24-hour dispatch schedule produced by the solver.
    total_cost_bdt : float
        Total operational cost in BDT.
    peak_grid_kwh : float
        Peak hourly grid import in kWh.
    execution_time_ms : float
        Total execution latency in milliseconds.

    Returns
    -------
    dict or None
        Inserted row data if successful, None otherwise.
    """
    try:
        client = get_supabase_client()
        if client is None:
            return None

        record = {
            "scenario_id": str(scenario_id),
            "input_payload": _to_json_compatible(input_payload),
            "directive_interpretation": _to_json_compatible(directive_interpretation),
            "hourly_plan": _to_json_compatible(hourly_plan),
            "total_cost_bdt": float(total_cost_bdt),
            "peak_grid_kwh": float(peak_grid_kwh),
            "execution_time_ms": float(execution_time_ms),
        }

        # Offload synchronous PostgREST call to thread pool to preserve event-loop concurrency
        result = await asyncio.to_thread(
            lambda: client.table("optimization_logs").insert(record).execute()
        )
        return result.data if hasattr(result, "data") else None

    except Exception as exc:
        logger.warning(
            "Supabase logging failed for scenario '%s' (%s: %s). Request unaffected.",
            scenario_id,
            type(exc).__name__,
            exc,
        )
        return None


async def log_optimization_result(
    request: OptimizeEnergyRequest,
    response: OptimizeEnergyResponse,
    execution_time_ms: float,
) -> Optional[Dict[str, Any]]:
    """Convenience wrapper for BackgroundTasks taking typed request and response envelopes."""
    return await log_optimization_run(
        scenario_id=response.scenario_id,
        input_payload=request,
        directive_interpretation=response.directive_interpretation,
        hourly_plan=response.hourly_plan,
        total_cost_bdt=response.total_cost_bdt,
        peak_grid_kwh=response.peak_grid_kwh,
        execution_time_ms=execution_time_ms,
    )


__all__ = [
    "OPTIMIZATION_LOGS_DDL",
    "get_supabase_client",
    "log_optimization_run",
    "log_optimization_result",
]
