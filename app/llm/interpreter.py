"""LLM-based structured directive interpreter for operator notes.

Uses litellm for multi-provider support (Gemini, OpenAI, Anthropic, Groq, etc.)
with strict JSON schema enforcement, a 4.0-second timeout, and safe no_op fallbacks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

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
    """Generate safe fallback interpretations for notes using deterministic parser when possible.

    Ensures the service never crashes if the LLM times out or encounters errors.
    If deterministic parser recognizes directives, they are preserved; otherwise safe no_op is returned.
    """
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

    # Strip markdown fences if present
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    data = json.loads(cleaned)

    # Extract interpretations list from envelope or direct array
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

    # Validate each item through Pydantic
    parsed_items: List[DirectiveInterpretation] = [
        DirectiveInterpretation.model_validate(item) for item in raw_list
    ]

    # Verify and sort note_index order
    parsed_items.sort(key=lambda x: x.note_index)
    for expected_idx, item in enumerate(parsed_items):
        if item.note_index != expected_idx:
            raise ValueError(
                f"Missing or mismatched note_index. Expected {expected_idx}, got {item.note_index}."
            )

    return parsed_items


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


async def interpret_operator_notes(
    notes: List[str],
    battery: BatteryInput,
) -> List[DirectiveInterpretation]:
    """Parse unstructured operator notes into structured energy optimization directives.

    Parameters
    ----------
    notes : list[str]
        List of 1 to 3 operator notes.
    battery : BatteryInput
        Battery configuration used for relative reserve capacity calculations.

    Returns
    -------
    list[DirectiveInterpretation]
        Exactly one validated DirectiveInterpretation per note. If the LLM call times
        out (> 4.0 seconds) or fails, safe fallback no_op directives are returned.
    """
    if not notes:
        return []

    # Check and clean configured API keys
    gemini_key = _clean_credential(os.getenv("GEMINI_API_KEY")) or _clean_credential(getattr(settings, "GEMINI_API_KEY", None))
    openai_key = _clean_credential(os.getenv("OPENAI_API_KEY")) or _clean_credential(getattr(settings, "OPENAI_API_KEY", None))
    groq_key = _clean_credential(os.getenv("GROQ_API_KEY")) or _clean_credential(getattr(settings, "GROQ_API_KEY", None))
    google_key = _clean_credential(os.getenv("GOOGLE_API_KEY"))
    anthropic_key = _clean_credential(os.getenv("ANTHROPIC_API_KEY"))

    # Choose model
    model = os.getenv("LLM_MODEL", getattr(settings, "LLM_MODEL", "gemini/gemini-3.6-flash"))

    # If no key is set anywhere, quickly fallback with informative notice
    has_any_key = bool(gemini_key or openai_key or groq_key or google_key or anthropic_key)
    if not has_any_key:
        logger.warning(
            "No LLM API keys detected in environment. Returning safe fallback directives."
        )
        return build_fallback_interpretations(
            notes,
            battery=battery,
            reason="No LLM API key configured; defaulted to safe no_op",
        )

    # Determine api_key and ensure environment variable is present for litellm
    api_key: Optional[str] = None
    if "gemini" in model:
        api_key = gemini_key or google_key
        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key
    elif "openai" in model or "gpt" in model:
        api_key = openai_key
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
    elif "groq" in model:
        api_key = groq_key
        if api_key:
            os.environ["GROQ_API_KEY"] = api_key
    elif "claude" in model or "anthropic" in model:
        api_key = anthropic_key
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
    else:
        api_key = gemini_key or openai_key or groq_key or google_key or anthropic_key

    user_prompt = build_user_prompt(notes, battery)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        # Enforce strict 4.0-second timeout using asyncio.wait_for
        response = await asyncio.wait_for(
            litellm.acompletion(
                model=model,
                messages=messages,
                api_key=api_key,
                temperature=getattr(settings, "LLM_TEMPERATURE", 0.0),
                response_format=DirectiveInterpretationsEnvelope,
                timeout=STRICT_TIMEOUT_SECONDS,
            ),
            timeout=STRICT_TIMEOUT_SECONDS,
        )

        content: Optional[str] = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned empty response content.")

        return _clean_and_parse_json(content, expected_count=len(notes))

    except (asyncio.TimeoutError, TimeoutError) as e:
        logger.warning(
            "LLM call exceeded strict %.1fs timeout: %s", STRICT_TIMEOUT_SECONDS, e
        )
        return build_fallback_interpretations(
            notes,
            battery=battery,
            reason=f"LLM request timed out after {STRICT_TIMEOUT_SECONDS}s",
        )

    except Exception as e:
        logger.warning(
            "LLM interpretation error (%s: %s). Applying safe fallback.",
            type(e).__name__,
            e,
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
