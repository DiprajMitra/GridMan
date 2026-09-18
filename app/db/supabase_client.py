"""Supabase client and non-blocking background logger for optimization runs.

Persists scenario inputs, LLM directive interpretations, optimized schedules,
and performance metrics to Supabase PostgreSQL without blocking API responses.
Handles empty strings, quoted strings, and missing credentials gracefully.
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
    operator_notes JSONB NOT NULL,
    directive_interpretation JSONB NOT NULL,
    hourly_plan JSONB NOT NULL,
    total_grid_kwh NUMERIC(12, 4) NOT NULL,
    total_cost_bdt NUMERIC(12, 4) NOT NULL,
    peak_grid_kwh NUMERIC(10, 4) NOT NULL,
    plan_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Performance indexes for lookup and reporting
CREATE INDEX IF NOT EXISTS idx_optimization_logs_scenario_id ON optimization_logs (scenario_id);
CREATE INDEX IF NOT EXISTS idx_optimization_logs_created_at ON optimization_logs (created_at DESC);
"""

# Cached singleton client instance and state flag
_supabase_client: Optional[Client] = None
_client_init_attempted: bool = False


def _clean_credential(val: Optional[str]) -> Optional[str]:
    """Clean credential strings by stripping whitespace and literal quotes ('' or "")."""
    if val is None:
        return None
    cleaned = str(val).strip()
    # Strip enclosing single or double quotes
    while (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
        if len(cleaned) <= 1:
            return None
        cleaned = cleaned[1:-1].strip()
    if not cleaned or cleaned.lower() in ("none", "null", "undefined", "false", '""', "''"):
        return None
    return cleaned


def get_supabase_client() -> Optional[Client]:
    """Retrieve or initialize the Supabase client safely.

    Returns None gracefully if SUPABASE_URL or SUPABASE_SERVICE_KEY is unset, empty (""),
    whitespace-only, or invalid. Never raises uncaught exceptions.
    """
    global _supabase_client, _client_init_attempted
    if _supabase_client is not None:
        return _supabase_client
    if _client_init_attempted:
        return None

    # Retrieve and clean URL
    env_url = os.getenv("SUPABASE_URL")
    url = _clean_credential(env_url) if env_url is not None else _clean_credential(getattr(settings, "SUPABASE_URL", None))

    # Retrieve and clean Key
    env_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    key = _clean_credential(env_key) if env_key is not None else (
        _clean_credential(getattr(settings, "SUPABASE_SERVICE_KEY", None))
        or _clean_credential(getattr(settings, "SUPABASE_KEY", None))
    )

    if not url or not key:
        logger.debug("Supabase credentials not configured or empty; persistence disabled.")
        _client_init_attempted = True
        return None

    if not (url.startswith("http://") or url.startswith("https://")):
        logger.warning("Supabase URL '%s' is invalid; persistence disabled.", url)
        _client_init_attempted = True
        return None

    try:
        _supabase_client = create_client(url, key)
        _client_init_attempted = True
        return _supabase_client
    except Exception as exc:
        logger.warning("Failed to initialize Supabase client: %s", exc)
        _client_init_attempted = True
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
    execution_time_ms: float = 0.0,
    total_grid_kwh: float = 0.0,
    plan_summary: Optional[str] = None,
    operator_notes: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Persist an optimization run record into Supabase asynchronously.

    Designed for invocation within FastAPI BackgroundTasks. All database
    and network exceptions are safely trapped so logging failures never affect
    the API response.

    Supports both standard deployed schema (operator_notes, total_grid_kwh, plan_summary)
    and legacy fallback schema (input_payload, execution_time_ms).
    """
    try:
        client = get_supabase_client()
        if client is None:
            return None

        # Extract operator_notes if not explicitly passed
        if operator_notes is None:
            if isinstance(input_payload, dict):
                operator_notes = input_payload.get("operator_notes", [])
            elif hasattr(input_payload, "operator_notes"):
                operator_notes = input_payload.operator_notes
            else:
                operator_notes = []

        # Calculate total_grid_kwh if not provided
        if total_grid_kwh <= 0.0 and hourly_plan:
            calc_grid = 0.0
            for entry in hourly_plan:
                if isinstance(entry, dict):
                    calc_grid += float(entry.get("grid_kwh", entry.get("grid_import_kwh", 0.0)))
                elif hasattr(entry, "grid_kwh"):
                    calc_grid += float(entry.grid_kwh)
                elif hasattr(entry, "grid_import_kwh"):
                    calc_grid += float(entry.grid_import_kwh)
            if calc_grid > 0.0:
                total_grid_kwh = calc_grid

        # Primary record matching the deployed Supabase table schema
        primary_record = {
            "scenario_id": str(scenario_id),
            "operator_notes": _to_json_compatible(operator_notes),
            "directive_interpretation": _to_json_compatible(directive_interpretation),
            "hourly_plan": _to_json_compatible(hourly_plan),
            "total_grid_kwh": round(float(total_grid_kwh), 4),
            "total_cost_bdt": round(float(total_cost_bdt), 4),
            "peak_grid_kwh": round(float(peak_grid_kwh), 4),
            "plan_summary": str(plan_summary or ""),
        }

        try:
            result = await asyncio.to_thread(
                lambda: client.table("optimization_logs").insert(primary_record).execute()
            )
            return result.data if hasattr(result, "data") else None
        except Exception as insert_err:
            err_msg = str(insert_err).lower()
            # If the database table has an alternative schema (e.g. input_payload, execution_time_ms)
            if "operator_notes" in err_msg or "input_payload" in err_msg or "execution_time_ms" in err_msg:
                alt_record = {
                    "scenario_id": str(scenario_id),
                    "input_payload": _to_json_compatible(input_payload),
                    "directive_interpretation": _to_json_compatible(directive_interpretation),
                    "hourly_plan": _to_json_compatible(hourly_plan),
                    "total_cost_bdt": round(float(total_cost_bdt), 4),
                    "peak_grid_kwh": round(float(peak_grid_kwh), 4),
                    "execution_time_ms": round(float(execution_time_ms), 2),
                }
                result = await asyncio.to_thread(
                    lambda: client.table("optimization_logs").insert(alt_record).execute()
                )
                return result.data if hasattr(result, "data") else None
            raise

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
        total_grid_kwh=response.total_grid_kwh,
        plan_summary=response.plan_summary,
        operator_notes=request.operator_notes,
    )


__all__ = [
    "OPTIMIZATION_LOGS_DDL",
    "get_supabase_client",
    "log_optimization_run",
    "log_optimization_result",
]
