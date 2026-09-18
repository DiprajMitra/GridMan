"""API routes for GridWise energy optimization service."""

import logging
import time
from typing import Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.db.supabase_client import log_optimization_result
from app.llm.interpreter import interpret_operator_notes
from app.optimizer.guardrails import validate_and_sanitize_directives
from app.optimizer.solver import solve_schedule
from app.schemas.contract import (
    HealthResponse,
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
)

logger = logging.getLogger("gridwise.api.routes")

router = APIRouter(tags=["Optimization"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Returns service availability and status within 10ms.",
)
async def health_check() -> Dict[str, str]:
    """Instant health check endpoint returning HTTP 200 with status ok."""
    return {"status": "ok"}


@router.post(
    "/optimize-energy",
    response_model=OptimizeEnergyResponse,
    status_code=status.HTTP_200_OK,
    summary="Optimize 24-Hour Energy Dispatch",
    description="Processes operator notes through LLM extraction, applies guardrails, solves the LP schedule, and persists results.",
)
async def optimize_energy(
    request: OptimizeEnergyRequest,
    background_tasks: BackgroundTasks,
) -> OptimizeEnergyResponse:
    """Execute complete end-to-end 24-hour campus energy optimization pipeline.

    Pipeline Steps:
    1. Start precision latency timer.
    2. Extract raw operator directives using LLM interpreter.
    3. Validate and sanitize directives through domain guardrails.
    4. Solve mathematical LP dispatch schedule using HiGHS solver.
    5. Trigger non-blocking Supabase logging task in background.
    6. Return complete structured response with hourly plan and metrics.
    """
    start_time = time.perf_counter()

    try:
        # Step 1: Interpret operator notes with LLM
        raw_directives = await interpret_operator_notes(
            notes=request.operator_notes,
            battery=request.battery,
        )

        # Step 2: Validate and sanitize through guardrails
        sanitized_directives = validate_and_sanitize_directives(
            raw_interpretations=raw_directives,
            battery_capacity=request.battery.capacity_kwh,
        )

        # Step 3: Solve mathematical dispatch schedule
        response = solve_schedule(
            request=request,
            sanitized_directives=sanitized_directives,
        )
    except Exception as err:
        logger.error(
            "Optimization pipeline error for scenario '%s': %s",
            request.scenario_id,
            err,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred while processing the optimization request.",
        ) from None

    # Step 4: Calculate execution duration
    execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "Scenario '%s' optimized in %.2f ms (cost=%.2f BDT, peak=%.2f kWh)",
        request.scenario_id,
        execution_time_ms,
        response.total_cost_bdt,
        response.peak_grid_kwh,
    )

    # Step 5: Schedule asynchronous non-blocking Supabase persistence
    background_tasks.add_task(
        log_optimization_result,
        request=request,
        response=response,
        execution_time_ms=execution_time_ms,
    )

    # Step 6: Return structured response
    return response


__all__ = [
    "router",
]
