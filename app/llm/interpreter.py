"""LLM-based structured directive interpreter for operator notes.

Uses litellm for multi-provider support (Gemini, OpenAI, Anthropic, Groq, etc.)
with strict JSON schema enforcement, a 4.0-second timeout, multi-key rotation
on rate-limit errors, and safe no_op fallbacks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import litellm
from pydantic import BaseModel, Field

from app.core.config import settings
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from app.schemas.contract import (
    BatteryInput,
    DirectiveInterpretation,
    DirectiveType,
)

# Suppress verbose external telemetry logs
litellm.suppress_debug_info = True
litellm.drop_params = True

logger = logging.getLogger("gridwise.llm.interpreter")

STRICT_TIMEOUT_SECONDS: float = 4.0

# Retry strategy for transient rate limits (HTTP 429).
# Note: Gemini free tier limit is only 20 requests/day per model; once that daily
# quota is exhausted, retries cannot succeed within the same 24h window. The
# interpreter therefore distinguishes a per-minute/per-second "burst" 429
# (retryable, retryDelay is sub-minute) from a daily-quota 429 (non-retryable),
# and rotates to a different provider instead of just spinning on one.
#
# `RESOURCE_EXHAUSTED` alone is ambiguous (Google uses it for both per-minute
# bursts AND daily limits). It only counts as "daily exhausted" when paired
# with one of the more specific daily-quota markers.
_DAILY_QUOTA_MARKERS = (
    "GenerateRequestsPerDayPerProjectPerModel",
    "PerDayPerProjectPerModel-FreeTier",
    "free_tier_requests",
)
_BILLING_QUOTA_MARKERS = (
    "insufficient_quota",
    "quota_exceeded",
    "billing",
    "Payment Required",
    "plan quota",
)


def _is_daily_quota_exhausted(message: str) -> bool:
    """Detect provider daily/quota exhaustion (non-retryable within 24h or billing cycle)."""
    if not message:
        return False
    msg = message or ""
    has_daily = any(m in msg for m in _DAILY_QUOTA_MARKERS)
    has_billing = any(m in msg for m in _BILLING_QUOTA_MARKERS)
    return has_daily or has_billing


def _extract_retry_delay_seconds(message: str) -> Optional[float]:
    """Extract retryDelay seconds from the Gemini rate-limit error message."""
    if not message:
        return None
    match = re.search(r"retryDelay\"\s*:\s*\"\s*([0-9]+(?:\.[0-9]+)?)\s*s", message)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    match = re.search(r"Please retry in\s+([0-9]+(?:\.[0-9]+)?)\s*s", message)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Provider rotation
# ─────────────────────────────────────────────────────────────────────────────
#
# When one provider returns HTTP 429 / RESOURCE_EXHAUSTED / RateLimitError,
# we rotate to the next configured provider instead of falling back to the
# deterministic parser. The user requested the rotation order:
#   GROQ  →  OPENAI  →  GEMINI
#
# Per-process state:
#   - _provider_cooldowns[provider]: epoch time until which this provider is
#     considered "in cooldown" after a recent transient 429. While in cooldown
#     we skip the provider and try the next one. Cooldowns are short (~30 s)
#     and self-heal.
#   - _provider_exhausted: set of providers that have returned a non-retryable
#     daily-quota / billing error in this process lifetime. We never try them
#     again until the process restarts.

_PROVIDER_ORDER: Tuple[str, ...] = ("groq", "openai", "gemini")

# Default model per provider. Overridable via LLM_MODEL_<PROVIDER> env var.
_DEFAULT_MODELS: Dict[str, str] = {
    "groq": "groq/llama-3.3-70b-versatile",
    "openai": "gpt-4o-mini",
    "gemini": "gemini/gemini-2.0-flash",
}

# Env-var name per provider that litellm expects.
_PROVIDER_ENV_VAR: Dict[str, str] = {
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

# Short cooldown after a transient 429 so we don't immediately retry the same
# provider. Cooldown is in seconds.
_TRANSIENT_COOLDOWN_SECONDS: float = 30.0

_provider_cooldowns: Dict[str, float] = {}
_provider_exhausted: set[str] = set()
_rotator_lock = threading.Lock()


def _clean_credential(val: Optional[str]) -> Optional[str]:
    """Clean credential strings by stripping whitespace and literal quotes ('' or "")."""
    if val is None:
        return None
    cleaned = str(val).strip()
    while (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
        if len(cleaned) <= 1:
            return None
        cleaned = cleaned[1:-1].strip()
    if not cleaned or cleaned.lower() in ("none", "null", "undefined", "false", '""', "''"):
        return None
    return cleaned


def _get_api_key(provider: str) -> Optional[str]:
    """Read the configured API key for a provider from env or settings."""
    env_name = _PROVIDER_ENV_VAR.get(provider)
    if not env_name:
        return None
    env_val = os.getenv(env_name)
    # If the env var was explicitly deleted (monkeypatch.delenv) we must NOT
    # fall back to settings — that would resurrect a key the test deleted.
    if env_val is not None:
        return _clean_credential(env_val)
    return None


def _get_model(provider: str) -> str:
    """Resolve the model string for a provider.

    Precedence:
      1. LLM_MODEL_<PROVIDER> env var (e.g. LLM_MODEL_GROQ)
      2. Built-in default model for the provider
    """
    override = os.getenv(f"LLM_MODEL_{provider.upper()}")
    if override:
        return override
    return _DEFAULT_MODELS[provider]


def _build_provider_chain() -> List[Dict[str, str]]:
    """Build the list of available providers in rotation order.

    Excludes providers that:
      - have no API key configured
      - are marked as permanently exhausted in this process
      - are currently in cooldown
    """
    chain: List[Dict[str, str]] = []
    now = time.monotonic()
    for provider in _PROVIDER_ORDER:
        if provider in _provider_exhausted:
            continue
        cooldown_until = _provider_cooldowns.get(provider, 0.0)
        if cooldown_until > now:
            continue
        api_key = _get_api_key(provider)
        if not api_key:
            continue
        chain.append({
            "provider": provider,
            "model": _get_model(provider),
            "api_key": api_key,
            "env_var": _PROVIDER_ENV_VAR[provider],
        })
    return chain


def _mark_provider_rate_limited(provider: str, message: str) -> None:
    """Mark a provider as either transient-cooled or permanently exhausted."""
    with _rotator_lock:
        if _is_daily_quota_exhausted(message):
            _provider_exhausted.add(provider)
            logger.warning(
                "Provider '%s' marked as permanently exhausted for this process "
                "(daily/quota error). Will rotate to next provider.",
                provider,
            )
        else:
            _provider_cooldowns[provider] = (
                time.monotonic() + _TRANSIENT_COOLDOWN_SECONDS
            )
            logger.info(
                "Provider '%s' cooled down for %.0fs after transient 429.",
                provider, _TRANSIENT_COOLDOWN_SECONDS,
            )


def _is_rate_limit_error(exc: BaseException) -> bool:
    """Detect any rate-limit signal across the providers we use."""
    name = type(exc).__name__
    msg = str(exc) or ""
    return (
        "RateLimitError" in name
        or "RateLimit" in name
        or "429" in msg
        or "RESOURCE_EXHAUSTED" in msg
        or "RateLimitError" in msg
        or "rate_limit" in msg.lower()
        or "rate limit" in msg.lower()
    )


class DirectiveInterpretationsEnvelope(BaseModel):
    """Container envelope for LLM structured output parsing."""

    interpretations: List[DirectiveInterpretation] = Field(
        ...,
        description="List of interpreted directives, exactly one per input note.",
    )


def build_fallback_interpretations(
    notes: List[str],
    battery: Optional[BatteryInput] = None,
    reason: str = "LLM unavailable or timed out; safe fallback applied.",
) -> List[DirectiveInterpretation]:
    """Generate safe fallback interpretations for notes using deterministic parser when possible."""
    if battery is not None:
        try:
            from app.llm.parser import extract_directives_deterministically

            parsed = extract_directives_deterministically(notes, battery.capacity_kwh)
            results: List[DirectiveInterpretation] = []
            for idx, item in enumerate(parsed):
                if item.applies:
                    results.append(item)
                else:
                    results.append(
                        DirectiveInterpretation(
                            note_index=idx,
                            applies=False,
                            directive_type=DirectiveType.NO_OP,
                            structured_adjustment=None,
                            explanation=f"{reason} (Original note: {notes[idx][:80]})",
                        )
                    )
            return results
        except Exception as e:
            logger.warning("Deterministic fallback parsing error: %s", e)

    return [
        DirectiveInterpretation(
            note_index=idx,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation=f"{reason} (Original note: {notes[idx][:80]})",
        )
        for idx in range(len(notes))
    ]


def _clean_and_parse_json(content: str, expected_count: int) -> List[DirectiveInterpretation]:
    """Parse raw LLM string content into a validated list of DirectiveInterpretation objects."""
    cleaned = content.strip()

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    data = json.loads(cleaned)

    raw_list: List[Any]
    if isinstance(data, dict):
        if "interpretations" in data and isinstance(data["interpretations"], list):
            raw_list = data["interpretations"]
        elif "directives" in data and isinstance(data["directives"], list):
            raw_list = data["directives"]
        elif "results" in data and isinstance(data["results"], list):
            raw_list = data["results"]
        else:
            raw_list = [data]
    elif isinstance(data, list):
        raw_list = data
    else:
        raise ValueError(f"Unexpected JSON root structure: {type(data)}")

    if len(raw_list) != expected_count:
        raise ValueError(
            f"Expected {expected_count} interpretations, but LLM returned {len(raw_list)}."
        )

    parsed_items: List[DirectiveInterpretation] = [
        DirectiveInterpretation.model_validate(item) for item in raw_list
    ]

    parsed_items.sort(key=lambda x: x.note_index)
    for expected_idx, item in enumerate(parsed_items):
        if item.note_index != expected_idx:
            raise ValueError(
                f"Missing or mismatched note_index. Expected {expected_idx}, got {item.note_index}."
            )

    return parsed_items


async def _try_one_provider(
    provider_entry: Dict[str, str],
    messages: List[Dict[str, str]],
    temperature: float,
) -> Tuple[Optional[str], Optional[BaseException], bool]:
    """Attempt one LLM call on a single provider.

    Returns
    -------
    (content, error, is_rate_limit)
        content        — non-None only on success.
        error          — the underlying exception on failure.
        is_rate_limit  — True if the failure was a rate-limit / quota error.
    """
    provider = provider_entry["provider"]
    model = provider_entry["model"]
    api_key = provider_entry["api_key"]
    env_var = provider_entry["env_var"]

    os.environ[env_var] = api_key

    try:
        response = await asyncio.wait_for(
            litellm.acompletion(
                model=model,
                messages=messages,
                api_key=api_key,
                temperature=temperature,
                response_format=DirectiveInterpretationsEnvelope,
                timeout=STRICT_TIMEOUT_SECONDS,
            ),
            timeout=STRICT_TIMEOUT_SECONDS,
        )
        content = response.choices[0].message.content
        if not content:
            return None, ValueError("LLM returned empty response content."), False
        return content, None, False
    except (asyncio.TimeoutError, TimeoutError) as e:
        return None, e, False
    except Exception as e:
        is_rl = _is_rate_limit_error(e)
        return None, e, is_rl


async def interpret_operator_notes(
    notes: List[str],
    battery: BatteryInput,
) -> List[DirectiveInterpretation]:
    """Parse unstructured operator notes into structured energy optimization directives.

    Provider rotation
    -----------------
    Multiple LLM providers are supported in a fixed rotation order so that a
    transient 429 from one provider automatically falls through to the next:

        GROQ  →  OPENAI  →  GEMINI

    On a transient per-minute rate limit, the offending provider is placed in
    a short cooldown (~30 s) and the next provider is tried within the same
    request. On a daily / billing quota exhaustion, the provider is marked as
    permanently exhausted for the lifetime of this process and is skipped on
    future requests. The deterministic parser is the last-resort fallback used
    only when every configured provider has failed in this request.

    Parameters
    ----------
    notes : list[str]
        List of 1 to 3 operator notes.
    battery : BatteryInput
        Battery configuration used for relative reserve capacity calculations.

    Returns
    -------
    list[DirectiveInterpretation]
        Exactly one validated DirectiveInterpretation per note. If every LLM
        provider fails or times out, safe fallback no_op directives are
        returned.
    """
    if not notes:
        return []

    chain = _build_provider_chain()
    if not chain:
        logger.warning(
            "No LLM providers available (no API keys configured or all exhausted). "
            "Returning safe fallback directives."
        )
        return build_fallback_interpretations(
            notes,
            battery=battery,
            reason="No LLM provider available; defaulted to safe no_op",
        )

    temperature = getattr(settings, "LLM_TEMPERATURE", 0.0)
    max_retries_per_provider = int(getattr(settings, "LLM_MAX_RETRIES", 1))

    user_prompt = build_user_prompt(notes, battery)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    last_error: Optional[BaseException] = None
    attempted_providers: List[str] = []

    try:
        for provider_entry in chain:
            provider = provider_entry["provider"]
            attempted_providers.append(provider)
            logger.info(
                "LLM attempt via provider '%s' (model='%s')",
                provider, provider_entry["model"],
            )

            for attempt in range(max_retries_per_provider + 1):
                content, error, is_rl = await _try_one_provider(
                    provider_entry, messages, temperature,
                )

                if content is not None:
                    try:
                        return _clean_and_parse_json(content, expected_count=len(notes))
                    except (ValueError, json.JSONDecodeError) as parse_err:
                        last_error = parse_err
                        logger.warning(
                            "Provider '%s' returned unparseable JSON (attempt %d): %s",
                            provider, attempt + 1, parse_err,
                        )
                        if attempt < max_retries_per_provider:
                            await asyncio.sleep(0.5)
                            continue
                        break

                if error is None:
                    break

                last_error = error

                if is_rl:
                    _mark_provider_rate_limited(provider, str(error))
                    logger.warning(
                        "Provider '%s' hit rate limit (attempt %d/%d): %s",
                        provider, attempt + 1, max_retries_per_provider + 1, error,
                    )
                    # Respect the per-provider retry budget: if we have more
                    # attempts available AND this looks like a transient
                    # (per-minute) limit (not a daily-quota exhaustion), wait
                    # briefly and retry on the same provider. After the budget
                    # is exhausted, break out and rotate to the next provider.
                    if (
                        attempt < max_retries_per_provider
                        and not _is_daily_quota_exhausted(str(error))
                    ):
                        suggested = _extract_retry_delay_seconds(str(error))
                        backoff = min(suggested, 2.0) if suggested is not None else 1.0
                        await asyncio.sleep(backoff)
                        continue
                    logger.info(
                        "Provider '%s' exhausted retry budget; rotating.",
                        provider,
                    )
                    break

                if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
                    logger.warning(
                        "Provider '%s' timed out (attempt %d/%d): %s",
                        provider, attempt + 1, max_retries_per_provider + 1, error,
                    )
                    if attempt < max_retries_per_provider:
                        await asyncio.sleep(1.0)
                        continue
                    break

                logger.warning(
                    "Provider '%s' returned non-rate-limit error (%s: %s). Rotating.",
                    provider, type(error).__name__, error,
                )
                break

        # All providers tried without success. Apply deterministic fallback so
        # the optimizer still produces a valid schedule.
        providers_str = ", ".join(attempted_providers) if attempted_providers else "none"
        logger.warning(
            "All LLM providers failed (tried: %s). Last error: %s. "
            "Applying deterministic fallback.",
            providers_str, last_error,
        )
        # Include the last error's class name in the explanation so callers
        # can distinguish schema/JSON errors from rate-limit errors.
        err_class = type(last_error).__name__ if last_error is not None else "Unknown"
        reason = (
            f"LLM providers exhausted (tried: {providers_str}, "
            f"last error: {err_class}); applied deterministic fallback"
        )
        return build_fallback_interpretations(notes, battery=battery, reason=reason)

    except Exception as e:
        logger.warning(
            "LLM interpretation unexpected error (%s: %s). Applying safe fallback.",
            type(e).__name__, e,
        )
        return build_fallback_interpretations(
            notes,
            battery=battery,
            reason=f"LLM extraction error ({type(e).__name__})",
        )


__all__ = [
    "DirectiveInterpretationsEnvelope",
    "build_fallback_interpretations",
    "interpret_operator_notes",
]
