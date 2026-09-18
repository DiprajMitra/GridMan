"""Main FastAPI application for GridWise Energy Optimization Service.

BUP CSE Fest 2026 Specification Conforming Implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import settings

# Configure structured application logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gridwise.main")

# ============================================================================
# FastAPI Application Factory
# ============================================================================

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Campus energy dispatch optimization API conforming strictly to BUP CSE Fest 2026 specifications.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ============================================================================
# Middleware
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Custom Exception Handlers
# ============================================================================


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return HTTP 400 Bad Request for structurally invalid or malformed request payloads."""
    errors = exc.errors()
    simplified_errors = [
        {
            "loc": list(err.get("loc", [])),
            "msg": err.get("msg", "Validation error"),
            "type": err.get("type", "value_error"),
        }
        for err in errors
    ]
    logger.warning("Validation error on %s %s: %s", request.method, request.url.path, simplified_errors)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": simplified_errors,
            "message": "Malformed JSON or structurally invalid input data.",
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(
    request: Request, exc: ValueError
) -> JSONResponse:
    """Return HTTP 400 Bad Request when domain validation rules are violated."""
    logger.warning("Value error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": str(exc),
            "message": "Request parameter constraint violation.",
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Return controlled HTTP 500 response without leaking internal secrets, API keys, or raw stack traces."""
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred while processing the optimization request.",
            "message": "Internal server error. No sensitive diagnostic data is disclosed.",
        },
    )


# ============================================================================
# Mount Routers
# ============================================================================

# Mount at root to serve /health and /optimize-energy directly as specified
app.include_router(router)

# Also mount under API_PREFIX (e.g. /api) for reverse proxy flexibility
if settings.API_PREFIX:
    app.include_router(router, prefix=settings.API_PREFIX)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
