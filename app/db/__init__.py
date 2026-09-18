"""Database package for GridWise persistence."""

from app.db.supabase_client import (
    OPTIMIZATION_LOGS_DDL,
    get_supabase_client,
    log_optimization_result,
    log_optimization_run,
)

__all__ = [
    "OPTIMIZATION_LOGS_DDL",
    "get_supabase_client",
    "log_optimization_run",
    "log_optimization_result",
]
